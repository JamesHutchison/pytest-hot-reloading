from typing import Callable, Generator, Optional

workarounds = []


def register_workaround(func: Callable[[list[str]], Optional[Generator]]) -> None:
    """
    Register a workaround. A workaround is a function that takes in
    a list of the arguments passed into pytest. The function may
    be a generator function, and if so, yield will separate the pre
    and post calls.
    """
    workarounds.append(func)


@register_workaround
def xdist_workaround() -> Generator:
    """
    pytest-xdist is not supported. The test collection behaves differently
    and some libraries such as pytest-django may have bugs when its enabled.
    """
    try:
        pass
    except ImportError:
        return  # not installed
    from xdist import plugin

    # monkey patch to force zero processes
    plugin.parse_numprocesses = lambda s: None


@register_workaround
def pytest_django_tox_workaround() -> Generator:
    """
    pytest-django will attempt to add a suffix and they will accumulate with each run.
    Note that running tox with hot reloading doesn't make sense anyways.
    """
    try:
        import pytest_django  # noqa
    except ImportError:
        return

    from pytest_django import fixtures

    # monkey patch to disable suffix logic used by xdist and tox
    fixtures._set_suffix_to_test_databases = lambda suffix: None


def run_workarounds_pre() -> list[Generator]:
    in_progress_workarounds = []
    for workaround in workarounds:
        result = workaround()
        if result is not None:
            next(result)
            in_progress_workarounds.append(result)
    return in_progress_workarounds


def run_workarounds_post(in_progress_workarounds: list[Generator]) -> None:
    for workaround in in_progress_workarounds:
        try:
            next(workaround)
        except StopIteration:
            pass
