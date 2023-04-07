import json
import socket


class PytestClient:
    def __init__(self, daemon_host: str = "localhost", daemon_port: int = 4852) -> None:
        self._socket = None
        self._daemon_host = daemon_host
        self._daemon_port = daemon_port

    def run(self, args: list[str]) -> str:
        self._start_daemon_if_needed()

        # Connect to the daemon
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((self._daemon_host, self._daemon_port))

        # send the args to the daemon using json
        self._socket.sendall(json.dumps(args).encode())

        # Receive the message from the daemon
        data = self._socket.recv(1024)
        return data.decode("utf-8")

    def abort(self) -> None:
        # Close the socket
        self._socket.close()

    def _start_daemon_if_needed(self) -> None:
        # check if the daemon is running on the expected host and port
        # if not, start the daemon

        # first, try to connect
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect((self._daemon_host, self._daemon_port))
        except ConnectionRefusedError:
            # the daemon is not running
            # start the daemon
            self._start_daemon()
        else:
            # the daemon is running
            # close the socket
            self._socket.close()

    def _start_daemon(self) -> None:
        # start the daemon


    # def run_test(self, item):
    #     # Send the test to the daemon
    #     self._socket.sendall(item.name.encode())

    #     # Receive the message from the daemon
    #     data = self._socket.recv(1024)
    #     print(data)

    # def pytest_collection(self, session):
    #     # if the daemon is not running, start it
    #     if not self._daemon.is_running():
    #         self._daemon.start()

    #     # This is the entry point for the daemon
    #     # It will run the tests in a loop
    #     # The daemon will be stopped by the user
    #     # or by the client
    #     daemon = Daemon()
    #     daemon.run_loop()
