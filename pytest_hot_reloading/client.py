import json
import os
import socket
import sys
import time
import xmlrpc.client
from pathlib import Path
from typing import Sequence, cast


class PytestClient:
    _socket: socket.socket | None
    _daemon_host: str
    _daemon_port: int
    _pytest_name: str
    _will_start_daemon_if_needed: bool
    _do_not_autowatch_fixtures: bool
    _use_os_events: bool

    def __init__(
        self,
        daemon_host: str = "localhost",
        daemon_port: int = 4852,
        pytest_name: str = "pytest",
        start_daemon_if_needed: bool = False,
        do_not_autowatch_fixtures: bool = False,
        use_os_events: bool = False,
        poll_throttle: float = 1.0,
        additional_args: Sequence[str] = [],
    ) -> None:
        self._socket = None
        self._daemon_host = daemon_host
        self._daemon_port = daemon_port
        self._pytest_name = pytest_name
        self._will_start_daemon_if_needed = start_daemon_if_needed
        self._do_not_autowatch_fixtures = do_not_autowatch_fixtures
        self._use_os_events = use_os_events
        self._additional_args = additional_args
        self._poll_throttle = poll_throttle

    def _get_server(self) -> xmlrpc.client.ServerProxy:
        server_url = f"http://{self._daemon_host}:{self._daemon_port}"
        server = xmlrpc.client.ServerProxy(server_url)

        return server

    def run(self, cwd: Path, args: list[str]) -> int:
        if self._will_start_daemon_if_needed:
            self._start_daemon_if_needed()
        elif not self._daemon_running():
            raise Exception(
                "Daemon is not running and must be started, or add --daemon-start-if-needed"
            )

        server = self._get_server()

        env = os.environ.copy()
        sys_path = sys.path

        start = time.time()
        result: dict = cast(dict, server.run_pytest(str(cwd), json.dumps(env), sys_path, args))
        print(f"Daemon took {(time.time() - start):.3f} seconds to reply")

        stdout = result["stdout"].data.decode("utf-8")
        stderr = result["stderr"].data.decode("utf-8")

        print(stdout, file=sys.stdout)
        print(stderr, file=sys.stderr)

        return result["status_code"]

    def stop(self) -> None:
        """
        Stop the daemon
        """
        server = self._get_server()

        try:
            server.stop()
        except OSError:
            print("Daemon is not running")
        else:
            print("Daemon stopped")

    def abort(self) -> None:
        # Close the socket
        if self._socket:
            self._socket.close()

    def _daemon_running(self) -> bool:
        # first, try to connect
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect((self._daemon_host, self._daemon_port))
            # the daemon is running
            # close the socket
            self._socket.close()
            return True
        except ConnectionRefusedError:
            # the daemon is not running
            return False

    def _start_daemon_if_needed(self) -> None:
        # check if the daemon is running on the expected host and port
        # if not, start the daemon
        if not self._daemon_running():
            self._start_daemon()

    def _start_daemon(self) -> None:
        from pytest_hot_reloading.daemon import PytestDaemon

        # start the daemon
        PytestDaemon.start(
            host=self._daemon_host,
            port=self._daemon_port,
            pytest_name=self._pytest_name,
            do_not_autowatch_fixtures=self._do_not_autowatch_fixtures,
            use_os_events=self._use_os_events,
            additional_args=self._additional_args,
            poll_throttle=self._poll_throttle,
        )
