import json
import socket
import sys
import time
import urllib.request
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

    def run_robyn(self, args: list[str]) -> str:
        self._start_daemon_if_needed()

        def make_http_request(url, data):
            import time

            start = time.time()
            # import requests

            # response = requests.post(url, json=data)

            # Encode the data as a JSON string
            json_data = json.dumps(data).encode("utf-8")

            # Set the headers
            headers = {"Content-Type": "application/json"}

            request = urllib.request.Request(url, data=json_data, headers=headers, method="POST")
            response = urllib.request.urlopen(request)

            # Read the response data
            response_data = response.read()

            # Close the response
            response.close()

            ret = json.loads(response_data.decode("utf-8"))  # Convert bytes to string
            print(time.time() - start)
            return ret

        server_url = f"http://{self._daemon_host}:{self._daemon_port}/pytest/"
        # result = json.loads()
        result = make_http_request(server_url, args)

        stdout = result["stdout"]
        stderr = result["stderr"]

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
        start = time.time()
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
        print(f"Daemon check: {time.time() - start}")

    def _start_daemon(self) -> None:
        # start the daemon
        PytestDaemon.start(
            host=self._daemon_host, port=self._daemon_port, pytest_name=self._pytest_name
        )
