import threading
import time
from collections.abc import Callable
from typing import Any

WEB_CLIENT_TTL_S = 90


class Lifecycle:
    def __init__(
        self,
        idle_timeout_min: float,
        auto_exit: bool,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.idle_timeout_min = idle_timeout_min
        self.auto_exit = auto_exit
        self._clock = clock
        self._lock = threading.Lock()
        self._jobs = 0
        self._last_end = clock()
        self._last_heartbeat: float | None = None
        self._unloaded = False

    def begin_job(self) -> None:
        with self._lock:
            self._jobs += 1
            self._unloaded = False

    def end_job(self) -> None:
        with self._lock:
            self._jobs = max(0, self._jobs - 1)
            self._last_end = self._clock()

    def heartbeat(self) -> None:
        self._last_heartbeat = self._clock()

    def web_client_active(self) -> bool:
        beat = self._last_heartbeat
        return beat is not None and self._clock() - beat <= WEB_CLIENT_TTL_S

    def idle_s(self) -> float:
        with self._lock:
            if self._jobs:
                return 0.0
            return self._clock() - self._last_end

    def tick(self, service: Any, exit_fn: Callable[[], None]) -> str:
        with self._lock:
            if self._jobs or self._clock() - self._last_end < self.idle_timeout_min * 60:
                return "none"
            if self.auto_exit and not self.web_client_active():
                action = "exit"
            elif self._unloaded:
                return "none"
            else:
                self._unloaded = True
                action = "unload"
        if action == "exit":
            exit_fn()
        else:
            service.unload_models()
        return action
