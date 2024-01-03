def test_always_ran():
    pass


def test_adding_fixture(added_fixture):
    """
    This test uses a fixture that is added

    Should pass
    """


async def test_adding_fixture_async(async_added_fixture):
    """
    This test uses an async fixture that is added

    Should pass
    """


def test_removing_fixture(removed_fixture):
    """
    This test uses a fixture that is removed and no longer uses it

    Should pass
    """


async def test_removing_fixture_async(async_removed_fixture):
    """
    This test uses an async fixture that is removed and no longer uses it

    Should pass
    """


def test_removing_should_fail(removed_fixture):
    """
    This test uses a removed fixture

    Should error
    """


def test_renaming_fixture(renamed_fixture):
    """
    This test uses a fixture that is renamed

    Should pass
    """


def test_renaming_should_fail(renamed_fixture):
    """
    This test uses a fixture that is renamed without updating it here

    Should fail
    """


def test_fixture_changes_dependency(dependency_change_fixture):
    """
    This test uses a fixture that changes its dependencies

    Should pass
    """
    assert dependency_change_fixture == 2222


def test_fixture_has_dependency_renamed(dependency_change_fixture):
    """
    This test uses a fixture that renamed a dependency

    Should pass
    """
    assert dependency_change_fixture == 1


def test_fixture_removes_dependency(dependency_removed_fixture):
    """
    This test uses a fixture that removes a dependency

    Should pass
    """


def test_fixture_has_dependency_removed(dependency_removed_fixture):
    """
    This test uses a fixture that removes a dependency without updating it here

    Should fail
    """


def test_fixture_outside_of_conftest(fixture_outside_of_conftest):
    """
    This test uses a fixture that is modified outside of conftest.py

    Should pass
    """
    assert fixture_outside_of_conftest == "modified value"


def test_autouse_fixture_outside_of_conftest_is_removed(fixture_outside_of_conftest):
    """
    This test uses a fixture that is altered by an autouse fixture outside of context

    Should pass
    """
    assert fixture_outside_of_conftest == "modified by autouse value"


class TestClass:
    def test_method_fixture_change(self, renamed_fixture):
        """
        This test uses a fixture that is renamed

        Should pass
        """
