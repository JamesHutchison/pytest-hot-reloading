# A pytest plugin that starts the daemon if needed and forwards the args
# to the daemon. The plugin will wait for the response from the daemon.
# the daemon is communicated with using a tcp socket.
# The daemon is started in a separate process and the plugin will wait
# for the daemon to start before continuing.
# if the daemon is busy on a test, subsequent tests will be queued
# If the user runs the exact same test within 0.5 seconds, the daemon
# will take that as a signal to restart proir to running the second
# test. This plugin prevents the normal pytest logic from running.
# Pytest can also be ran with the "--daemon" argument to start the daemon
# in which case this isn't the client but the daemon itself. This
# is useful if you want to run with debugging. If you run
# the daemon with "--using-debug", then clients that run with the "--using-debug"
# option will send the message to the debug client.


# The plugin hook
import os
import sys

from pytest import Session

from pytest_hot_reloading.client import PytestClient
from pytest_hot_reloading.daemon import PytestDaemon

# this is modified by the daemon so that the pytest_collection hooks does not run
i_am_server = False


def pytest_addoption(parser) -> None:
    group = parser.getgroup("daemon")
    group.addoption(
        "--daemon",
        action="store_true",
        default=False,
        help="Start the daemon",
    )
    group.addoption(
        "--using-debug",
        action="store_true",
        default=False,
        help="Use the debug client port. This overrides --daemon-port.",
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


# list of pytest hooks
# https://docs.pytest.org/en/stable/reference.html#_pytest.hookspec.pytest_addhooks


def pytest_collection(session: Session) -> None:
    if session.config.option.collectonly:
        return
    if i_am_server:
        return
    _plugin_logic(session)


def _plugin_logic(session: Session) -> None:
    # if daemon is passed, then we are the daemon
    # if daemon is not passed, then we are the client
    daemon_port = int(session.config.option.daemon_port)
    if session.config.option.using_debug:
        daemon_port = 4853
    if session.config.option.daemon:
        # pytest prints out "collecting ...". The leading \r prevents that
        print("\rStarting daemon...")
        daemon = PytestDaemon(daemon_port=daemon_port)
        daemon.run_forever()
    else:
        pytest_name = session.config.option.pytest_name
        client = PytestClient(daemon_port=daemon_port, pytest_name=pytest_name)
        # find the index of the first value that is not None
        for idx, val in enumerate([pytest_name in x for x in sys.argv]):
            if val:
                pytest_name_index = idx
                break
        else:
            print(sys.argv)
            raise Exception(
                "Could not find pytest name in args. "
                "Check the configured name versus the actual name."
            )
        client.run(sys.argv[pytest_name_index:])

        # dont do any more work. Don't let pytest continue
        os._exit(0)
