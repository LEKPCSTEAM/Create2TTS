import fcntl
import json
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from .config import Settings, data_dir, load_settings
from .models import Preset, SynthRequest, SynthResult, Voice, WorkerStatus

HEALTH_TIMEOUT_S = 2
JOB_TIMEOUT_S = 600

_spawn_lock = threading.Lock()


class WorkerError(Exception):
    pass


def _default_spawn() -> None:
    log = open(data_dir() / "worker.log", "ab")
    subprocess.Popen(
        [sys.executable, "-m", "create2tts.cli", "serve", "--auto-exit"],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=log,
    )
    log.close()


class WorkerClient:
    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
        spawn: Callable[[], None] | None = None,
    ):
        self.settings = settings or load_settings()
        self.base_url = f"http://{self.settings.host}:{self.settings.port}"
        self._spawn = spawn or _default_spawn
        self._http = httpx.Client(base_url=self.base_url, transport=transport, timeout=JOB_TIMEOUT_S)

    def is_running(self) -> bool:
        try:
            return self._http.get("/api/health", timeout=HEALTH_TIMEOUT_S).status_code == 200
        except httpx.HTTPError:
            return False

    def ensure_running(self, timeout_s: float = 60) -> None:
        if self.is_running():
            return
        with _spawn_lock, open(data_dir() / "worker.lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                if self.is_running():
                    return
                self._spawn()
                deadline = time.monotonic() + timeout_s
                while time.monotonic() < deadline:
                    if self.is_running():
                        return
                    time.sleep(0.5)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
        raise WorkerError(f"worker did not start within {timeout_s:g}s (see data/worker.log)")

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            resp = self._http.request(method, path, **kwargs)
        except httpx.HTTPError as e:
            raise WorkerError(f"worker unreachable at {self.base_url}: {e}") from e
        if resp.status_code >= 400:
            raise WorkerError(_error_detail(resp))
        return resp

    def list_voices(self) -> list[Voice]:
        return [Voice.model_validate(v) for v in self._request("GET", "/api/voices").json()]

    def list_presets(self) -> list[Preset]:
        return [Preset.model_validate(p) for p in self._request("GET", "/api/presets").json()]

    def synthesize(self, req: SynthRequest) -> SynthResult:
        body = req.model_dump(mode="json", exclude_none=True)
        return SynthResult.model_validate(self._request("POST", "/api/synthesize", json=body).json())

    def clone_voice(self, name: str, audio_path: Path, ref_text: str | None = None, language: str = "th") -> Voice:
        data = {"name": name, "language": language}
        if ref_text:
            data["ref_text"] = ref_text
        with open(audio_path, "rb") as f:
            resp = self._request("POST", "/api/voices", data=data, files={"file": (Path(audio_path).name, f)})
        return Voice.model_validate(resp.json())

    def convert(self, audio_path: Path, language: str, **fields) -> SynthResult:
        request = {k: v for k, v in fields.items() if v is not None}
        data = {"language": language, "request": json.dumps(request)}
        with open(audio_path, "rb") as f:
            resp = self._request("POST", "/api/convert", data=data, files={"file": (Path(audio_path).name, f)})
        return SynthResult.model_validate(resp.json())

    def delete_voice(self, id: str) -> None:
        self._request("DELETE", f"/api/voices/{id}")

    def status(self) -> WorkerStatus:
        return WorkerStatus.model_validate(self._request("GET", "/api/status").json())

    def shutdown(self) -> None:
        self._request("POST", "/api/shutdown")


def _error_detail(resp: httpx.Response) -> str:
    try:
        detail = resp.json()["detail"]
    except (ValueError, KeyError, TypeError):
        return f"HTTP {resp.status_code}: {resp.text[:200]}"
    return detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)
