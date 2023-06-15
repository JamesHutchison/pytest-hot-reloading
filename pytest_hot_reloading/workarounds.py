from typing import Callable, Generator, Optional

workarounds: list[Callable[[], Optional[Generator]]] = []


def register_workaround(func: Callable[[], Optional[Generator]]) -> None:
    """
    Register a workaround. A workaround is a function that takes in
    a list of the arguments passed into pytest. The function may
    be a generator function, and if so, yield will separate the pre
    and post calls.
    """
    workarounds.append(func)


@register_workaround
def xdist_workaround() -> None:
    """
    pytest-xdist is not supported. The test collection behaves differently
    and some libraries such as pytest-django may have bugs when its enabled.
    """
    try:
        from xdist import plugin  # type: ignore
    except ImportError:
        return  # not installed

    # monkey patch to force zero processes
    plugin.parse_numprocesses = lambda s: None


@register_workaround
def pytest_django_tox_workaround() -> None:
    """
    pytest-django will attempt to add a suffix and they will accumulate with each run.
    Note that running tox with hot reloading doesn't make sense anyways.
    """
    try:
        from pytest_django import fixtures  # type: ignore
    except ImportError:
        return  # not installed

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
