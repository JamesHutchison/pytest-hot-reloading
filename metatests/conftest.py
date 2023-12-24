import pytest


@pytest.fixture()  # start of removed fixture
def removed_fixture():
    """
    This fixture is removed
    """
    a = 1
    pass


@pytest.fixture()  # start of async removed fixture
async def async_removed_fixture():
    """
    This fixture is removed
    """


@pytest.fixture()
def renamed_fixture():
    """
    This fixture is renamed
    """


@pytest.fixture()
def dependency_change_fixture(dependency_fixture):
    """
    This fixture changes its dependencies
    """
    return dependency_fixture


@pytest.fixture()  # start of dependency fixture
def dependency_fixture():
    """
    This fixture is a dependency
    """
    return 1  # dependency value


@pytest.fixture()
def dependency_removed_fixture(dependency_fixture):
    """
    This fixture removes a dependency
    """
    return 1
