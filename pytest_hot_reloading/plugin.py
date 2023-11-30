"""
Pytest Hot Reloading plugin
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from pytest_hot_reloading.client import PytestClient

# this is modified by the daemon so that the pytest_collection hooks does not run
i_am_server = False

seen_paths: set[Path] = set()

if TYPE_CHECKING:
    from pytest import Config, Item, Session


def pytest_addoption(parser) -> None:
    group = parser.getgroup("daemon")
    group.addoption(
        "--daemon",
        action="store_true",
        default=False,
        help="Start the daemon. If it is already running, the old instance will stop.",
    )
    group.addoption(
        "--daemon-port",
        action="store",
        default=int(os.getenv("PYTEST_DAEMON_PORT", "4852")),
        help="The port to use for the daemon. You generally shouldn't need to set this.",
    )
    group.addoption(
        "--pytest-name",
        action="store",
        default=os.getenv("PYTEST_DAEMON_PYTEST_NAME", "pytest"),
        help="The name of the pytest executable or module. This is used for starting the daemon.",
    )
    group.addoption(
        "--daemon-timeout",
        action="store",
        default=os.getenv("PYTEST_DAEMON_TIMEOUT", (5 * 60)),
        help="The timeout in seconds to wait on a test suite to finish. This is not yet implemented.",
    )
    group.addoption(
        "--daemon-watch-globs",
        action="store",
        default=os.getenv("PYTEST_DAEMON_WATCH_GLOBS", "./*.py"),
        help="The globs to watch for changes. This is a colon separated list of globs.",
    )
    group.addoption(
        "--daemon-ignore-watch-globs",
        action="store",
        default=os.getenv("PYTEST_DAEMON_IGNORE_WATCH_GLOBS", "./.venv/*"),
        help="The globs to ignore for changes. This is a colon separated list of globs.",
    )
    group.addoption(
        "--stop-daemon",
        action="store_true",
        default=False,
        help="Stop the daemon",
    )
    group.addoption(
        "--daemon-start-if-needed",
        action="store_true",
        default=os.getenv("PYTEST_DAEMON_START_IF_NEEDED", "False").lower() in ("true", "1"),
        help=(
            "Start the daemon if it is not running. To use this with VS Code, "
            'you need add "python.experiments.optOutFrom": ["pythonTestAdapter"] to your config.'
        ),
    )


# list of pytest hooks
# https://docs.pytest.org/en/stable/reference.html#_pytest.hookspec.pytest_addhooks


def pytest_cmdline_main(config: Config) -> Optional[int]:
    """
    This hook is called by pytest and is one of the first hooks.
    """
    # early escapes
    if config.option.collectonly:
        return None
    if i_am_server:
        return None
    if config.option.help:
        return None
    status_code = _plugin_logic(config)
    # dont do any more work. Don't let pytest continue
    return status_code  # status code 0


def monkey_patch_jurigged_function_definition():
    import jurigged.codetools as jurigged_codetools  # type: ignore
    import jurigged.utils as jurigged_utils  # type: ignore

    OrigFunctionDefinition = jurigged_codetools.FunctionDefinition

    import ast

    class NewFunctionDefinition(OrigFunctionDefinition):
        def reevaluate(self, new_node, glb):
            new_node = self.apply_assertion_rewrite(new_node, glb)
            obj = super().reevaluate(new_node, glb)
            return obj

        def apply_assertion_rewrite(self, ast_func, glb):
            from _pytest.assertion.rewrite import AssertionRewriter

            nodes: list[ast.AST] = [ast_func]  # type: ignore
            while nodes:
                node = nodes.pop()
                for name, field in ast.iter_fields(node):
                    if isinstance(field, list):
                        new: list[ast.AST] = []  # type: ignore
                        for i, child in enumerate(field):
                            if isinstance(child, ast.Assert):
                                # Transform assert.
                                new.extend(
                                    AssertionRewriter(glb["__file__"], None, None).visit(child)
                                )
                            else:
                                new.append(child)
                                if isinstance(child, ast.AST):
                                    nodes.append(child)
                        setattr(node, name, new)
                    elif (
                        isinstance(field, ast.AST)
                        # Don't recurse into expressions as they can't contain
                        # asserts.
                        and not isinstance(field, ast.expr)
                    ):
                        nodes.append(field)
            return ast_func

        def stash(self, lineno=1, col_offset=0):
            if not isinstance(self.parent, OrigFunctionDefinition):
                co = self.get_object()
                if co and (delta := lineno - co.co_firstlineno):
                    delta -= 1  # fix off-by-one
                    if delta > 0:
                        self.recode(jurigged_utils.shift_lineno(co, delta), use_cache=False)

            return super(OrigFunctionDefinition, self).stash(lineno, col_offset)

    # monkey patch in new definition
    jurigged_codetools.FunctionDefinition = NewFunctionDefinition


def setup_jurigged(config: Config):
    def _jurigged_logger(x: str) -> None:
        """
        Jurigged behavior is to both print and log.

        By default this creates duplicated output.

        Pass in a no-op logger to prevent this.
        """

    import jurigged

    monkey_patch_jurigged_function_definition()

    pattern = _get_pattern_filters(config)
    # TODO: intelligently use poll versus watchman (https://github.com/JamesHutchison/pytest-hot-reloading/issues/16)
    jurigged.watch(pattern=pattern, logger=_jurigged_logger, poll=True)


def _plugin_logic(config: Config) -> int:
    """
    The core plugin logic. This is where it splits based on whether we are the server or client.

    In either case, the pytest logic will not continue after this.
    """
    # if daemon is passed, then we are the daemon / server
    # if daemon is not passed, then we are the client
    daemon_port = int(config.option.daemon_port)
    if config.option.daemon:
        # pytest prints out "collecting ...". The leading \r prevents that
        print("\rStarting daemon...")
        setup_jurigged(config)

        from pytest_hot_reloading.daemon import PytestDaemon

        daemon = PytestDaemon(daemon_port=daemon_port)

        daemon.run_forever()
        sys.exit(0)
    else:
        pytest_name = config.option.pytest_name
        client = PytestClient(
            daemon_port=daemon_port,
            pytest_name=pytest_name,
            start_daemon_if_needed=config.option.daemon_start_if_needed,
        )

        if config.option.stop_daemon:
            client.stop()
            return 0

        cwd = config.invocation_params.dir
        args = list(config.invocation_params.args)

        status_code = client.run(cwd, args)
        return status_code


def _get_pattern_filters(config: Config) -> str | Callable[[str], bool]:
    """
    Jurigged takes in a pattern argument. The argument is either a glob string
    or a function that returns True if the path passed into it should be watched.

    This creates a function filter that will return True if the path matches.

    The logic takes in the --daemon-watch-globs and --daemon-ignore-watch-globs options
    and creates a function that will return True if the path matches the watch globs.

    The seen_paths set is used to prevent duplicate paths from being watched and also
    acts as a short circuit for paths that have already been seen.
    """
    global seen_paths

    import fnmatch
    import re

    def normalize(glob: str) -> str:
        if glob.startswith("~"):
            glob = os.path.expanduser(glob)
        elif not glob.startswith("/"):
            glob = os.path.abspath(glob)
        if os.path.isdir(glob):
            glob = os.path.join(glob, "*")
        return glob

    watch_globs = config.option.daemon_watch_globs.split(":")
    regex_matches = [re.compile(fnmatch.translate(normalize(glob))).match for glob in watch_globs]

    ignore_watch_globs = config.option.daemon_ignore_watch_globs
    if ignore_watch_globs:
        ignore_globs = config.option.daemon_ignore_watch_globs.split(":")
        ignore_regex_matches = [
            re.compile(fnmatch.translate(normalize(glob))).match for glob in ignore_globs
        ]
    else:
        ignore_regex_matches = []

    def matcher(filename: str) -> bool:
        if filename in seen_paths:
            return False
        seen_paths.add(Path(filename))
        if any(regex_match(filename) for regex_match in regex_matches):
            if not any(
                ignore_regex_match(filename) for ignore_regex_match in ignore_regex_matches
            ):
                return True
        return False

    return matcher


def pytest_collection_modifyitems(session: Session, config: Config, items: list[Item]) -> None:
    """
    This hooks is called by pytest after the collection phase.

    This adds tests to the watch list automatically.

    The client should never get this far. This should only be
    used by the daemon.
    """
    global seen_paths
    import jurigged

    for item in items:
        if item.path and item.path not in seen_paths:
            jurigged.watch(pattern=str(item.path))
            seen_paths.add(item.path)
