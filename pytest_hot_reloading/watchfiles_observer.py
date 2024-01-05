import time
from threading import Thread
from typing import Any

from jurigged.live import Watcher  # type: ignore
from watchfiles import Change, watch


class WatchfilesObserver:
    def __init__(
        self,
        watcher: Watcher,
        loop_sleep: float = 0.25,
        wait_group_ms: int = 500,
        wait_new_changes_ms: int = 150,
        rust_timeout: int = 2000,
        poll_delay_ms: int = 500,
        force_polling: bool = False,
    ) -> None:
        self._watching_dirs: set[str] = set()
        self._thread = None
        self._watcher = watcher
        self._loop_sleep = loop_sleep
        self._wait_group_ms = wait_group_ms
        self._wait_new_changes_ms = wait_new_changes_ms
        self._rust_timeout = rust_timeout
        self._poll_delay_ms = poll_delay_ms
        self._force_polling = force_polling

        self.__stop_signal = False

    def schedule(self, __handler: Any, directory: str) -> None:
        """
        Called by Jurigged when registering a file to watch. It actually
        calls the directory instead.

        :param __handler: The handler that is making the call. This is not used.
        :param directory: The directory to watch. The same directory may get repeated for every file
        """
        self._watching_dirs.add(directory)

    def start(self):
        self._thread = Thread(target=self._run)
        self._thread.start()

    def _run(self) -> None:
        prev_len = 0
        while True:
            for changes in watch(
                *self._watching_dirs,
                yield_on_timeout=True,
                debounce=self._wait_group_ms,
                step=self._wait_new_changes_ms,
                rust_timeout=self._rust_timeout,
                poll_delay_ms=self._poll_delay_ms,
                force_polling=self._force_polling,
                recursive=False,
            ):
                if self.__stop_signal:
                    return
                for change, path in changes:
                    if change in (Change.added, Change.modified):
                        if self._watcher.registry.get(path):
                            self._watcher.refresh(path)
                if len(self._watching_dirs) != prev_len:
                    prev_len = len(self._watching_dirs)
                    break
            if self.__stop_signal:
                return
            time.sleep(self._loop_sleep)

    def stop(self):
        self.__stop_signal = True

    def join(self):
        self.stop()
        self._thread.join()

    def __del__(self) -> None:
        try:
            self.join()
        except:
            pass
