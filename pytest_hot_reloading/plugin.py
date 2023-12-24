"""
Pytest Hot Reloading plugin
"""
from __future__ import annotations

import inspect
import os
import sys
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from pytest_hot_reloading.client import PytestClient
from pytest_hot_reloading.jurigged_daemon_signalers import JuriggedDaemonSignaler

# this is modified by the daemon so that the pytest_collection hooks does not run
i_am_server = False

seen_paths: set[Path] = set()
signaler = JuriggedDaemonSignaler()

if TYPE_CHECKING:
    from pytest import Config, Item, Parser, Session


class EnvVariables(str, Enum):
    PYTEST_DAEMON_PORT = "PYTEST_DAEMON_PORT"
    PYTEST_DAEMON_PYTEST_NAME = "PYTEST_DAEMON_PYTEST_NAME"
    PYTEST_DAEMON_TIMEOUT = "PYTEST_DAEMON_TIMEOUT"
    PYTEST_DAEMON_WATCH_GLOBS = "PYTEST_DAEMON_WATCH_GLOBS"
    PYTEST_DAEMON_IGNORE_WATCH_GLOBS = "PYTEST_DAEMON_IGNORE_WATCH_GLOBS"
    PYTEST_DAEMON_START_IF_NEEDED = "PYTEST_DAEMON_START_IF_NEEDED"
    PYTEST_DAEMON_DISABLE = "PYTEST_DAEMON_DISABLE"
    PYTEST_DAEMON_DO_NOT_AUTOWATCH_FIXTURES = "PYTEST_DAEMON_DO_NOT_AUTOWATCH_FIXTURES"
    PYTEST_DAEMON_USE_WATCHMAN = "PYTEST_DAEMON_USE_WATCHMAN"


def pytest_addoption(parser) -> None:
    group = parser.getgroup("daemon")
    group.addoption(
        "--daemon",
        action="store_true",
        default=False,
        help="Start the daemon. If it is already running, the old instance will stop.",
    )
    group.addoption(
        "--daemon-disable",
        action="store_true",
        default=(os.getenv(EnvVariables.PYTEST_DAEMON_DISABLE, "False").lower() in ("true", "1")),
        help="Do not use the daemon for this test run.",
    )
    group.addoption(
        "--daemon-port",
        action="store",
        default=int(os.getenv(EnvVariables.PYTEST_DAEMON_PORT, "4852")),
        help="The port to use for the daemon. You generally shouldn't need to set this.",
    )
    group.addoption(
        "--pytest-name",
        action="store",
        default=os.getenv(EnvVariables.PYTEST_DAEMON_PYTEST_NAME, "pytest"),
        help="The name of the pytest executable or module. This is used for starting the daemon.",
    )
    group.addoption(
        "--daemon-timeout",
        action="store",
        default=os.getenv(EnvVariables.PYTEST_DAEMON_TIMEOUT, (5 * 60)),
        help="The timeout in seconds to wait on a test suite to finish. This is not yet implemented.",
    )
    group.addoption(
        "--daemon-watch-globs",
        action="store",
        default=os.getenv(EnvVariables.PYTEST_DAEMON_WATCH_GLOBS, "./*.py"),
        help="The globs to watch for changes. This is a colon separated list of globs.",
    )
    group.addoption(
        "--daemon-ignore-watch-globs",
        action="store",
        default=os.getenv(EnvVariables.PYTEST_DAEMON_IGNORE_WATCH_GLOBS, "./.venv/*"),
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
        default=(
            os.getenv(EnvVariables.PYTEST_DAEMON_START_IF_NEEDED, "False").lower()
            in ("true", "1")
        ),
        help=(
            "Start the daemon if it is not running. To use this with VS Code, "
            'you need add "python.experiments.optOutFrom": ["pythonTestAdapter"] to your config.'
        ),
    )
    group.addoption(
        "--daemon-do-not-autowatch-fixtures",
        action="store_true",
        default=(
            os.getenv(EnvVariables.PYTEST_DAEMON_DO_NOT_AUTOWATCH_FIXTURES, "False").lower()
            in ("true", "1")
        ),
        help=(
            "Do not automatically watch fixtures. "
            "Typically this would be used if there's too many fixtures and the watch glob is used instead."
        ),
    )
    group.addoption(
        "--daemon-use-watchman",
        action="store_true",
        default=(
            os.getenv(EnvVariables.PYTEST_DAEMON_USE_WATCHMAN, "False").lower() in ("true", "1")
        ),
        help=(
            "Use watchman instead of polling. "
            "This reduces CPU usage, takes up open file handles, and improves responsiveness. "
            "Some systems cannot reliably use this."
        ),
    )


# list of pytest hooks
# https://docs.pytest.org/en/stable/reference.html#_pytest.hookspec.pytest_addhooks


def do_early_escape(config: Config) -> bool:
    if getattr(config.option, "collectonly", None):
        return True
    if i_am_server:
        return True
    if getattr(config.option, "help", None):
        return True
    if config.option.daemon_disable:
        return True
    return False


def pytest_load_initial_conftests(early_config: Config, args: list[str], parser: Parser) -> None:
    if do_early_escape(early_config):
        return
    early_config.known_args_namespace.noconftest = True


def pytest_cmdline_main(config: Config) -> Optional[int]:
    """
    This hook is called by pytest and is one of the first hooks.
    """
    if do_early_escape(config):
        return None
    status_code = _plugin_logic(config)
    # dont do any more work. Don't let pytest continue
    return status_code  # status code 0


fixture_names: set[str] = set()


def monkey_patch_jurigged_function_definition():
    import jurigged.codetools as jurigged_codetools  # type: ignore
    import jurigged.utils as jurigged_utils  # type: ignore

    OrigFunctionDefinition = jurigged_codetools.FunctionDefinition
    OrigDeleteOperation = jurigged_codetools.DeleteOperation

    import ast

    class NewDeleteOperation(OrigDeleteOperation):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)

            self._signal_clear_cache_if_fixture()

        def _signal_clear_cache_if_fixture(self) -> None:
            """
            Clear the cache if a fixture is deleted.

            If this isn't here, then deleted fixtures may still exist.
            """
            if self.defn.name in fixture_names:
                signaler.signal_clear_cache()

    class NewFunctionDefinition(OrigFunctionDefinition):
        def reevaluate(self, new_node, glb):
            func = glb[new_node.name]
            is_test = new_node.name.startswith("test_")
            if is_test:
                old_sig = inspect.signature(func)
            else:
                if new_node.name in fixture_names:
                    # if a fixture is updated, then clear the session cache to avoid stale responses
                    signaler.signal_clear_cache()
            # monkeypatch: The assertion rewrite is from pytest. Jurigged doesn't
            #              seem to have a way to add rewrite hooks
            new_node = self.apply_assertion_rewrite(new_node, glb)
            obj = super().reevaluate(new_node, glb)

            if is_test:
                new_sig = inspect.signature(func)

            # if the signature changes, clear the session cache
            # otherwise pytest will use the old signature.
            # This is a more of a band-aid because the session cache
            # could be more intelligently updated based on what was changed.
            # This band-aid fixes tests using stale fixture info, which
            # can result in unpredictable behavior that requires
            # restarting the daemon.
            if is_test:
                if old_sig != new_sig:
                    signaler.signal_clear_cache()

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
            # monkeypatch: There's an off-by-one bug coming from somewhere in jurigged.
            #              This affects replaced functions. When line numbers are wrong
            #              the debugger and inspection logic doesn't work as expected.
            if not isinstance(self.parent, OrigFunctionDefinition):
                co = self.get_object()
                if co and (delta := lineno - co.co_firstlineno):
                    delta -= 1  # fix off-by-one
                    if delta != 0:
                        self.recode(jurigged_utils.shift_lineno(co, delta), use_cache=False)

            return super(OrigFunctionDefinition, self).stash(lineno, col_offset)

    # monkey patch in new definition
    jurigged_codetools.FunctionDefinition = NewFunctionDefinition
    jurigged_codetools.DeleteOperation = NewDeleteOperation


def monkeypatch_group_definition():
    import jurigged.codetools as jurigged_codetools  # type: ignore

    def append(self, *children, ensure_separation=False):
        for child in children:
            # ensure_separation creates line number diff
            # an example where this was a problem:
            #
            # 15 class MyClass:
            # 77     do_something()  # type: ignore  <--- blank line inserted between do_something() and comment
            # 78
            # 79     def my_func(...)  <--- becomes line 80
            #
            # the monkey patch removes it
            #
            # removed code:
            # if (
            #     ensure_separation
            #     and self.children
            #     and not self.children[-1].well_separated(child)
            # ):
            #     ws = LineDefinition(
            #         node=None, text="\n", filename=self.filename
            #     )
            #     self.children.append(ws)
            #     ws.set_parent(self)
            self.children.append(child)
            child.set_parent(self)

    jurigged_codetools.GroupDefinition.append = append


def _jurigged_logger(x: str) -> None:
    """
    Jurigged behavior is to both print and log.

    By default this creates duplicated output.

    Pass in a no-op logger to prevent this.
    """
    print(x)


def setup_jurigged(config: Config):
    import jurigged

    monkey_patch_jurigged_function_definition()
    monkeypatch_group_definition()
    if not config.option.daemon_do_not_autowatch_fixtures:
        monkeypatch_fixture_marker(config.option.daemon_use_watchman)
    else:
        print("Not autowatching fixtures")

    pattern = _get_pattern_filters(config)
    # TODO: intelligently use poll versus watchman (https://github.com/JamesHutchison/pytest-hot-reloading/issues/16)
    jurigged.watch(
        pattern=pattern, logger=_jurigged_logger, poll=(not config.option.daemon_use_watchman)
    )


seen_files: set[str] = set()


def monkeypatch_fixture_marker(use_watchman: bool):
    import jurigged
    import pytest
    from _pytest import fixtures

    FixtureFunctionMarkerOrig = fixtures.FixtureFunctionMarker

    # FixtureFunctionMarker is marked as final
    class FixtureFunctionMarkerNew(FixtureFunctionMarkerOrig):  # type: ignore # noqa
        def __call__(self, func, *args, **kwargs):
            fixture_names.add(func.__name__)

            return super().__call__(func, *args, **kwargs)

    fixture_original = pytest.fixture

    # doing a pure class only monkeypatch was breaking event_loop fixture
    # so patching out fixture function to use new class
    def _new_fixture(*args, **kwargs):
        # get current file where this is called
        frame = inspect.stack()[1]
        module = inspect.getmodule(frame[0])
        fixture_file = module.__file__

        # add fixture file to watched files
        if fixture_file not in seen_files:
            seen_files.add(fixture_file)
            jurigged.watch(pattern=fixture_file, logger=_jurigged_logger, poll=(not use_watchman))

        fixtures.FixtureFunctionMarker = FixtureFunctionMarkerNew
        try:
            ret = fixture_original(*args, **kwargs)
        finally:
            fixtures.FixtureFunctionMarker = FixtureFunctionMarkerOrig

        return ret

    pytest.fixture = _new_fixture


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

        daemon = PytestDaemon(daemon_port=daemon_port, signaler=signaler)

        daemon.run_forever()
        sys.exit(0)
    else:
        pytest_name = config.option.pytest_name
        client = PytestClient(
            daemon_port=daemon_port,
            pytest_name=pytest_name,
            start_daemon_if_needed=config.option.daemon_start_if_needed,
            do_not_autowatch_fixtures=config.option.daemon_do_not_autowatch_fixtures,
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
    This hook is called by pytest after the collection phase.

    This adds tests and conftests to the watch list automatically.

    The client should never get this far. This should only be
    used by the daemon.
    """
    global seen_paths
    import jurigged

    for item in items:
        if item.path and item.path not in seen_paths:
            jurigged.watch(
                pattern=str(item.path),
                logger=_jurigged_logger,
                poll=(not config.option.daemon_use_watchman),
            )
            seen_paths.add(item.path)
