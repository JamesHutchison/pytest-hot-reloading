import time
from functools import lru_cache

from megamock import MegaMock, MegaPatch  # type: ignore


@lru_cache()
def do_setup() -> None:
    time.sleep(3)


def test_simple() -> None:
    do_setup()

    val = 1
    other_val = 1

    assert val == other_val, f"{val} != {other_val}"

    # seeing a jurigged bug where doing a hard coded assertion of 1 == 1 doesn't quite work right:
    # failing scenario
    # assert 1 == 1
    # assert 1 == 2
    # assert 1 == 1  (again)
    # This will still fail on the last assert, even though it should pass

    print("foo")


class AClassForMegaMockTesting:
    def a_method(self) -> str:
        return "val"


def test_megamock_usage():
    patch = MegaPatch.it(AClassForMegaMockTesting.a_method, return_value="returned value")
    patch.mock.return_value = "else"

    assert AClassForMegaMockTesting().a_method() == "else"

    mocked_class = MegaMock.it(AClassForMegaMockTesting)
    mocked_class.a_method.return_value = "another_val"

    assert mocked_class.a_method() == "another_val"
