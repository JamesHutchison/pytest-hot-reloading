import copy
import math
import os
import re
import socket
import subprocess
import sys
import time
from collections import UserDict, deque
from typing import Counter
from xmlrpc.server import SimpleXMLRPCServer

import pytest
from cachetools import LRUCache, TTLCache


class PytestDaemon:
    def __init__(self, daemon_host: str = "localhost", daemon_port: int = 4852) -> None:
        self._daemon_host = daemon_host
        self._daemon_port = daemon_port

    @property
    def pid_file(self) -> str:
        return f".pytest_hot_reloading_{self._daemon_port}.pid"

    @staticmethod
    def start(
        host: str,
        port: int,
        pytest_name: str = "pytest",
        watch_globs: str | None = None,
        ignore_watch_globs: str | None = None,
    ) -> None:
        # start the daemon such that it will not close when the parent process closes
        if host == "localhost":
            args = [
                sys.executable,
                "-m",
                pytest_name,
                "--daemon",
                "--daemon-port",
                str(port),
            ]
            if watch_globs:
                args += ["--daemon-watch-globs", watch_globs]
            if ignore_watch_globs:
                args += ["--daemon-ignore-watch-globs", ignore_watch_globs]
            subprocess.Popen(
                args,
                env=os.environ,
                cwd=os.getcwd(),
            )
        else:
            raise NotImplementedError("Only localhost is supported for now")
        PytestDaemon.wait_to_be_ready(host, port)

    @staticmethod
    def wait_to_be_ready(host: str = "localhost", port: int = 4852) -> None:
        # poll the connection to the daemon using sockets
        # and return when it is ready
        for _ in range(100):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((host, port))
            except ConnectionRefusedError:
                time.sleep(0.1)
                continue
            else:
                break
        else:
            raise Exception("Could not connect to the daemon")

    def run_forever(self) -> None:  # create an XML-RPC server
        try:
            server = SimpleXMLRPCServer((self._daemon_host, self._daemon_port))
        except OSError as err:
            if "Address already in use" in str(err):
                self._kill_existing_daemon()
                time.sleep(2)
                server = SimpleXMLRPCServer((self._daemon_host, self._daemon_port))

        self._write_pid_file()

        # register the 'run_pytest' function
        server.register_function(self.run_pytest, "run_pytest")

        server.serve_forever()

    def _write_pid_file(self) -> None:
        with open(self.pid_file, "w") as f:
            f.write(str(os.getpid()))

    def _kill_existing_daemon(self) -> None:
        try:
            with open(self.pid_file, "r") as f:
                pid = int(f.read())
            os.kill(pid, 9)
        except FileNotFoundError:
            raise Exception(f"Port {self._daemon_port} is already in use")

    def run_pytest(self, args: list[str]) -> dict:
        # run pytest using command line args
        # run the pytest main logic

        self._workaround_library_issues(args)

        import pytest_hot_reloading.plugin as plugin

        # indicate to the plugin to NOT run custom pytest collect logic
        plugin.i_am_server = True

        # capture stdout and stderr
        # and return the output
        import io

        stdout = io.StringIO()
        stderr = io.StringIO()

        # backup originals
        stdout_bak = sys.stdout
        stderr_bak = sys.stderr

        sys.stdout = stdout
        sys.stderr = stderr

        import _pytest.main

        # monkeypatch in the main that does test collection caching
        orig_main = _pytest.main._main
        _pytest.main._main = _pytest_main

        try:
            # args must omit the calling program
            pytest.main(["--color=yes"] + args)
        finally:
            # restore originals
            _pytest.main._main = orig_main

            sys.stdout = stdout_bak
            sys.stderr = stderr_bak

            stdout.seek(0)
            stderr.seek(0)
            stdout_str = stdout.read()
            stderr_str = stderr.read()

            print(stdout_str, file=sys.stdout)
            print(stderr_str, file=sys.stderr)
        return {
            "stdout": self._remove_ansi_escape(stdout_str).encode("utf-8"),
            "stderr": self._remove_ansi_escape(stderr_str).encode("utf-8"),
        }

    def _remove_ansi_escape(self, s: str) -> str:
        return re.sub(r"\x1b(\[.*?[@-~]|\].*?(\x07|\x1b\\))", "", s, flags=re.MULTILINE)

    def _workaround_library_issues(self, args: list[str]) -> None:
        # load modules that workaround library issues, as needed
        pass


session_item_cache = TTLCache(16, 500)
# hack: keeping a session cache since pytest has session references
#       littered everywhere on objects
prior_sessions = set()


def _manage_prior_session_garbage(session: pytest.Session) -> None:
    """
    Pytest creates a bunch of objects and nodes and assigns the session
    to them. This creates a lot of dangling references to sessions that
    can come up later due to reuse. To work around this, all prior
    sessions have their dicts updated to point to the latest session.

    To avoid accumulating too many sessions and taking up memory as well
    as runtime, this cleans out all the sessions that appear to be redundant.

    This isn't quite perfect but should maybe be enough. There's likely some
    corner cases where the session with the fewest references doesn't meet the
    count requirement. There may also be cases where the smallest session
    has something important on it and we don't want to clean it up, but it
    gets cleaned up anyways.

    The use case that drew attention to this problem was an autouse session
    fixture. The fixture's request object was referencing the session that
    used the fixture, which at some point in the flow creates a problem
    because that old session is not properly set up anymore.
    """
    ref_counts = {
        prior_session: sys.getrefcount(prior_session) for prior_session in prior_sessions
    }
    counts = Counter(ref_counts.values())
    min_count = min(counts.keys()) if ref_counts else 0

    for prior_session in list(prior_sessions):
        if (
            len(prior_sessions) > 5
            and counts[min_count] > 3
            and ref_counts[prior_session] <= min_count
        ):
            prior_sessions.remove(prior_session)
        else:
            prior_session.__dict__ = session.__dict__


def _pytest_main(config: pytest.Config, session: pytest.Session):
    """
    A monkey patched version of _pytest._main that caches test collection
    """
    _manage_prior_session_garbage(session)

    import _pytest.capture

    _pytest.capture.CaptureManager.stop_global_capturing = lambda self: None
    start_global_capturing = _pytest.capture.CaptureManager.start_global_capturing
    resume_global_capture = _pytest.capture.CaptureManager.resume_global_capture

    def start_global_capture_if_needed(self: _pytest.capture.CaptureManager):
        if self._global_capturing is None:
            start_global_capturing(self)
        return resume_global_capture(self)

    _pytest.capture.CaptureManager.resume_global_capture = start_global_capture_if_needed

    def best_effort_copy(item, depth_remaining=2):
        """
        Copy test items. The items have references to modules and
        other things that cannot be deep copied.
        """
        if depth_remaining <= 0:
            return item
        try:
            item_copy = copy.copy(item)
        except TypeError:
            return item
        # NodeKeywords is an example of an object without a __dict__
        if hasattr(item, "__dict__"):
            for k, v in item.__dict__.items():
                try:
                    item_copy.__dict__[k] = copy.deepcopy(v)
                except KeyboardInterrupt:
                    raise
                except TypeError:
                    # Non-pickelable objects
                    item_copy.__dict__[k] = best_effort_copy(v, depth_remaining - 1)
        return item_copy

    # here config.args becomes basically the tests to run. Other arguments are omitted
    # not 100% sure this is always the case
    session_key = tuple(config.args)
    try:
        items = session_item_cache[session_key]
    except KeyError:
        # not in the cache, do test collection
        start = time.time()
        config.hook.pytest_collection(session=session)
        print(f"Pytest Daemon: Collection took {(time.time() - start):0.3f} seconds")
        session_item_cache[session_key] = tuple(best_effort_copy(x) for x in session.items)
    else:
        print("Pytest Daemon: Using cached collection")
        # Assign the prior test items (tests to run) and config to the current session
        session.items = items
        session.config = config
        for i in items:
            # Items have references to the config and the session
            i.config = config
            i.session = session
            if i._request:
                i._request._pyfuncitem = i
    config.hook.pytest_runtestloop(session=session)
    prior_sessions.add(session)

    if session.testsfailed:
        return pytest.ExitCode.TESTS_FAILED
    elif session.testscollected == 0:
        return pytest.ExitCode.NO_TESTS_COLLECTED
    return None
