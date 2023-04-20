import time
from functools import lru_cache


@lru_cache()
def do_setup() -> None:
    time.sleep(3)


def test_simple() -> None:
    do_setup()
    assert 1 == 1
