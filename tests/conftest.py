import time

import pytest


@pytest.fixture(autouse=True, scope="session")
def some_session_fixture():
    yield


# if conftest loading is happening, then even simple tests will see this delay
time.sleep(2)
