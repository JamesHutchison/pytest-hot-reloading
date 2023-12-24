class JuriggedDaemonSignaler:
    def __init__(self) -> None:
        self._do_cache_clear = False
        self._deleted_fixtures: set[str] = set()

    def signal_clear_cache(self) -> None:
        self._do_cache_clear = True

    def receive_clear_cache_signal(self) -> bool:
        ret = self._do_cache_clear
        self._do_cache_clear = False
        return ret
