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
from pytest import Session

from pytest_hot_reloading.client import PytestClient
from pytest_hot_reloading.daemon import PytestDaemon


def pytest_addoption(parser):
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
        help="Use the debug client",
    )


# list of pytest hooks
# https://docs.pytest.org/en/stable/reference.html#_pytest.hookspec.pytest_addhooks


def pytest_collection(session: Session):
    # if daemon is passed, then we are the daemon
    # if daemon is not passed, then we are the client
    daemon_port = 4852
    if session.config.option.using_debug:
        daemon_port = 4853
    if session.config.option.daemon:
        daemon = PytestDaemon(daemon_port=daemon_port)
        daemon.run()
    else:
        client = PytestClient(daemon_port=daemon_port)
        client.run()


# The plugin hook
def pytest_configure(config):
    if config.option.daemon:
        # We are the daemon
        daemon = Daemon()
        daemon.run()
    else:
        # We are the client
        client = Client()
        client.run()


# The plugin hook
def pytest_unconfigure(config):
    if config.option.daemon:
        # We are the daemon
        daemon = Daemon()
        daemon.stop()
    else:
        # We are the client
        client = Client()
        client.stop()


# The plugin hook
def pytest_runtestloop(session):
    # This is the entry point for the daemon
    # It will run the tests in a loop
    # The daemon will be stopped by the user
    # or by the client
    daemon = Daemon()
    daemon.run_loop()


# The plugin hook
def pytest_runtest_protocol(item, nextitem):
    # This is the entry point for the client
    # It will send the test to the daemon
    # and wait for the response
    client = Client()
    client.run_test(item)
