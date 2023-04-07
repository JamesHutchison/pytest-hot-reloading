import socket
import subprocess
import time

import pytest


class PytestDaemon:
    def __init__(self, args: list[str]):
        self.args = args

    @staticmethod
    def start(host: str, port: int):
        # start the daemon such that it will not close when the parent process closes
        if host == "localhost":
            subprocess.Popen(
                [
                    "pytest",
                    "--daemon",
                    "--daemon-port",
                    str(port),
                ]
            )
        else:
            raise NotImplementedError("Only localhost is supported for now")
        PytestDaemon.wait_to_be_ready()

    @staticmethod
    def wait_to_be_ready(port: int):
        # poll the connection to the daemon using sockets
        # and return when it is ready
        for _ in range(1000):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect(("localhost", port))
            except ConnectionRefusedError:
                time.sleep(0.1)
                continue
            else:
                break
        else:
            raise Exception("Could not connect to the daemon")

    def run_loop(self) -> None:
        # run the daemon loop
        # the loop should run until the daemon is killed
        # the loop should:
        #   - accept a connection
        #   - receive the args
        #   - run pytest using the args
        #   - send the result
        #   - close the connection

        # create a socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # bind the socket to the host and port
        sock.bind(("localhost", 4852))

        # listen for connections
        sock.listen()

        while True:
            # accept a connection
            conn, addr = sock.accept()

            # receive the args
            args = conn.recv(1024)

            # run pytest using the args
            result = self.run_pytest(args)

            # send the result
            conn.sendall(result)

            # close the connection
            conn.close()

    def run_pytest(self, args: list[str]) -> None:
        # run pytest using command line args
        # run the pytest main logic

        self._workaround_library_issues(args)

        pytest.console_main(args)

    def _workaround_library_issues(self, args: list[str]) -> None:
        # load modules that workaround library issues, as needed
        pass
