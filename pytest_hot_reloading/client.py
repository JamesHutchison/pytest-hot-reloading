import socket
import sys
import xmlrpc.client

from pytest_hot_reloading.daemon import PytestDaemon


class PytestClient:
    _socket: socket.socket | None
    _daemon_host: str
    _daemon_port: int
    _pytest_name: str

    def __init__(
        self, daemon_host: str = "localhost", daemon_port: int = 4852, pytest_name: str = "pytest"
    ) -> None:
        self._socket = None
        self._daemon_host = daemon_host
        self._daemon_port = daemon_port
        self._pytest_name = pytest_name

    def run(self, args: list[str]) -> str:
        self._start_daemon_if_needed()

        server_url = f"http://{self._daemon_host}:{self._daemon_port}"
        server = xmlrpc.client.ServerProxy(server_url)

        result = server.run_pytest(args)

        stdout = result["stdout"].data.decode("utf-8")
        stderr = result["stderr"].data.decode("utf-8")

        print(stdout, file=sys.stdout)
        print(stderr, file=sys.stderr)

    def abort(self) -> None:
        # Close the socket
        if self._socket:
            self._socket.close()

    def _start_daemon_if_needed(self) -> None:
        # check if the daemon is running on the expected host and port
        # if not, start the daemon

        # first, try to connect
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect((self._daemon_host, self._daemon_port))
            # the daemon is running
            # close the socket
            self._socket.close()
        except ConnectionRefusedError:
            # the daemon is not running
            # start the daemon
            self._start_daemon()

    def _start_daemon(self) -> None:
        # start the daemon
        PytestDaemon.start(
            host=self._daemon_host, port=self._daemon_port, pytest_name=self._pytest_name
        )
