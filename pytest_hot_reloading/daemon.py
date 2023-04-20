import os
import socket
import subprocess
import sys
import time
from xmlrpc.server import SimpleXMLRPCServer

import pytest


class PytestDaemon:
    def __init__(self, daemon_host: str = "localhost", daemon_port: int = 4852) -> None:
        self._daemon_host = daemon_host
        self._daemon_port = daemon_port

    @property
    def pid_file(self) -> str:
        return f".pytest_hot_reloading_{self._daemon_port}.pid"

    @staticmethod
    def start(host: str, port: int, pytest_name: str = "pytest") -> None:
        # start the daemon such that it will not close when the parent process closes
        if host == "localhost":
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    pytest_name,
                    "--daemon",
                    "--daemon-port",
                    str(port),
                ],
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

        try:
            pytest.main(["--color=yes"] + args)
        finally:
            # restore originals
            sys.stdout = stdout_bak
            sys.stderr = stderr_bak

        stdout.seek(0)
        stderr.seek(0)
        stdout_str = stdout.read()
        stderr_str = stderr.read()

        print(stdout_str, file=sys.stdout)
        print(stderr_str, file=sys.stderr)
        return {
            "stdout": self._remove_ansi_escape(stdout_str),
            "stderr": self._remove_ansi_escape(stderr_str),
        }

    def _remove_ansi_escape(self, s: str) -> str:
        import re

        return re.sub(r"\x1b(\[.*?[@-~]|\].*?(\x07|\x1b\\))", "", s)

    def _workaround_library_issues(self, args: list[str]) -> None:
        # load modules that workaround library issues, as needed
        pass
