import pytest


@pytest.fixture(autouse=True, scope="session")
def some_session_fixture():
    yield
