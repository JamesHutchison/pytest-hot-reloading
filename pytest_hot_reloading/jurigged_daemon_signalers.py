import time


class JuriggedDaemonSignaler:
    def __init__(self) -> None:
        self._do_cache_clear = False
        self._deleted_fixtures: set[str] = set()
        self._block_until: float | None = None

    def signal_clear_cache(self) -> None:
        self._do_cache_clear = True
        self._block_until = time.time() + 1

    def receive_clear_cache_signal(self) -> bool:
        ret = self._do_cache_clear
        cur_time = time.time()
        while self._block_until is not None and cur_time < self._block_until:
            time.sleep(self._block_until - cur_time)
            cur_time = time.time()
        self._block_until = None
        self._do_cache_clear = False
        return ret
