"""
Pytest Hot Reloading plugin
"""
import fnmatch
import os
import re
import sys
from typing import Callable

import jurigged
from pytest import Config, Item, Session

from pytest_hot_reloading.client import PytestClient
from pytest_hot_reloading.daemon import PytestDaemon

# this is modified by the daemon so that the pytest_collection hooks does not run
i_am_server = False

seen_paths = set()


def pytest_addoption(parser) -> None:
    group = parser.getgroup("daemon")
    group.addoption(
        "--daemon",
        action="store_true",
        default=False,
        help="Start the daemon",
    )
    group.addoption(
        "--daemon-port",
        action="store",
        default=4852,
        help="The port to use for the daemon. You generally shouldn't need to set this.",
    )
    group.addoption(
        "--pytest-name",
        action="store",
        default="pytest",
        help="The name of the pytest executable or module",
    )
    group.addoption(
        "--daemon-timeout",
        action="store",
        default=(5 * 60),
        help="The timeout in seconds to wait on a test suite to finish",
    )
    group.addoption(
        "--daemon-watch-globs",
        action="store",
        default="./*.py",
        help="The globs to watch for changes. This is a colon separated list of globs.",
    )
    group.addoption(
        "--daemon-ignore-watch-globs",
        action="store",
        default="./.venv/*",
        help="The globs to ignore for changes. This is a colon separated list of globs.",
    )


# list of pytest hooks
# https://docs.pytest.org/en/stable/reference.html#_pytest.hookspec.pytest_addhooks


def pytest_collection(session: Session) -> None:
    """
    This hook is called by pytest and is one of the first hooks.
    """
    # early escapes
    if session.config.option.collectonly:
        return
    if i_am_server:
        return
    _plugin_logic(session)


def _jurigged_logger(x: str) -> None:
    """
    Jurigged behavior is to both print and log.

    By default this creates duplicated output.

    Pass in a no-op logger to prevent this.
    """


def _plugin_logic(session: Session) -> None:
    """
    The core plugin logic. This is where it splits based on whether we are the server or client.

    In either case, the pytest logic will not continue after this.
    """
    # if daemon is passed, then we are the daemon / server
    # if daemon is not passed, then we are the client
    daemon_port = int(session.config.option.daemon_port)
    if session.config.option.daemon:
        # pytest prints out "collecting ...". The leading \r prevents that
        print("\rStarting daemon...")
        pattern = _get_pattern_filters(session)
        jurigged.watch(pattern=pattern, logger=_jurigged_logger)
        daemon = PytestDaemon(daemon_port=daemon_port)
        daemon.run_forever()
    else:
        pytest_name = session.config.option.pytest_name
        client = PytestClient(daemon_port=daemon_port, pytest_name=pytest_name)
        # find the index of the first value that is not None
        for idx, val in enumerate(
            [
                x.endswith(pytest_name) or x.endswith(f"{pytest_name}/__main__.py")
                for x in sys.argv
            ]
        ):
            if val:
                pytest_name_index = idx
                break
        else:
            print(sys.argv)
            raise Exception(
                "Could not find pytest name in args. "
                "Check the configured name versus the actual name."
            )
        client.run(sys.argv[pytest_name_index + 1 :])

        # dont do any more work. Don't let pytest continue
        os._exit(0)


def _get_pattern_filters(session: Session) -> str | Callable[[str], bool]:
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

    def normalize(glob: str) -> str:
        if glob.startswith("~"):
            glob = os.path.expanduser(glob)
        elif not glob.startswith("/"):
            glob = os.path.abspath(glob)
        if os.path.isdir(glob):
            glob = os.path.join(glob, "*")
        return glob

    watch_globs = session.config.option.daemon_watch_globs.split(":")
    regex_matches = [re.compile(fnmatch.translate(normalize(glob))).match for glob in watch_globs]

    ignore_watch_globs = session.config.option.daemon_ignore_watch_globs
    if ignore_watch_globs:
        ignore_globs = session.config.option.daemon_ignore_watch_globs.split(":")
        ignore_regex_matches = [
            re.compile(fnmatch.translate(normalize(glob))).match for glob in ignore_globs
        ]
    else:
        ignore_regex_matches = []

    def matcher(filename) -> bool:
        if filename in seen_paths:
            return False
        seen_paths.add(filename)
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
    """
    global seen_paths

    for item in items:
        if item.path and item.path not in seen_paths:
            jurigged.watch(pattern=str(item.path))
            seen_paths.add(item.path)
