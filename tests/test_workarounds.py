from typing import Callable

import pytest  # type: ignore
from megamock import MegaPatch  # type: ignore

from pytest_hot_reloading import workarounds


@pytest.fixture(autouse=True)
def clear_workarounds() -> None:
    new_workarounds: list[Callable] = []
    MegaPatch.it(workarounds.workarounds, new=new_workarounds)


def test_single_shot_workaround() -> None:
    was_called = False

    @workarounds.register_workaround("tests.test_workarounds")
    def my_workaround():
        nonlocal was_called

        was_called = True

    in_progress = workarounds.run_workarounds_pre()
    assert len(in_progress) == 0
    workarounds.run_workarounds_post(in_progress)

    assert was_called


def test_multi_part_workaround() -> None:
    status = 0

    @workarounds.register_workaround("tests.test_workarounds")
    def my_workaround():
        nonlocal status

        status += 1
        yield
        status += 1

    in_progress = workarounds.run_workarounds_pre()
    assert len(in_progress) == 1
    workarounds.run_workarounds_post(in_progress)

    assert status == 2


def test_not_installed_workaround() -> None:
    was_called = False

    @workarounds.register_workaround("this.doesnt.exist")
    def my_workaround():
        nonlocal was_called

        was_called = True

    in_progress = workarounds.run_workarounds_pre()
    assert len(in_progress) == 0
    workarounds.run_workarounds_post(in_progress)

    assert was_called is False


def test_unregistered_workaround() -> None:
    was_called = False

    @workarounds.register_workaround("tests.workarounds.unregistered_workaround")
    def my_workaround():
        nonlocal was_called

        was_called = True

    workarounds.run_workarounds_pre()

    assert was_called is False
