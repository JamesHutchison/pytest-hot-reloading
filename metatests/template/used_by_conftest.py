from pytest import fixture

value_modified_by_autouse_fixture = "original value"


@fixture()
def fixture_outside_of_conftest() -> str:
    return value_modified_by_autouse_fixture


@fixture(autouse=True)
def autouse_fixture_outside_of_conftest() -> None:
    global value_modified_by_autouse_fixture
    value_modified_by_autouse_fixture = "modified by autouse value"
