import json
import os
import re
import signal
import threading
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from importlib import metadata
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import config
from ..models import (
    Preset,
    SynthRequest,
    SynthResult,
    TranscribeResult,
    Voice,
    VoiceUpdate,
    WorkerStatus,
)
from .lifecycle import Lifecycle

FILE_RE = re.compile(r"^[\w.-]+$")
PROTECTED_PRESET = "neutral"
MISSING_STATIC_HTML = (
    "<!doctype html><meta charset='utf-8'><title>Create2TTS</title>"
    "<p>ยังไม่ได้สร้างหน้าเว็บ กรุณารัน <code>cd web &amp;&amp; npm install &amp;&amp; npm run build</code></p>"
)


def _version() -> str:
    try:
        return metadata.version("create2tts")
    except metadata.PackageNotFoundError:
        return "0.0.0"


def _exit_via_sigterm() -> None:
    threading.Timer(0.3, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()


@contextmanager
def _upload(file: UploadFile):
    path = config.tmp_dir() / f"{uuid.uuid4().hex}{Path(file.filename or '').suffix}"
    path.write_bytes(file.file.read())
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


def _output_path(file: str) -> Path:
    root = config.outputs_dir().resolve()
    if not FILE_RE.fullmatch(file) or file.startswith("."):
        raise KeyError(file)
    path = (root / file).resolve()
    if path.parent != root:
        raise KeyError(file)
    return path


def create_app(
    service: Any,
    lifecycle: Lifecycle,
    static_dir: Path | None,
    exit_fn: Callable[[], None] = _exit_via_sigterm,
) -> FastAPI:
    app = FastAPI(title="Create2TTS worker")

    @app.exception_handler(KeyError)
    async def _not_found(_: Request, exc: KeyError):
        return JSONResponse({"detail": f"not found: {exc.args[0] if exc.args else ''}"}, status_code=404)

    @app.exception_handler(ValueError)
    async def _bad_request(_: Request, exc: ValueError):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @contextmanager
    def job():
        lifecycle.begin_job()
        try:
            yield
        finally:
            lifecycle.end_job()

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": _version(), "pid": os.getpid()}

    @app.get("/api/status")
    def status() -> WorkerStatus:
        return WorkerStatus(
            pid=os.getpid(),
            version=_version(),
            device=service.device,
            loaded_engines=service.loaded_engines(),
            busy=service.busy,
            idle_s=lifecycle.idle_s(),
            auto_exit=lifecycle.auto_exit,
            idle_timeout_min=lifecycle.idle_timeout_min,
            web_client=lifecycle.web_client_active(),
        )

    @app.get("/api/voices")
    def list_voices() -> list[Voice]:
        return service.voices.list()

    @app.post("/api/voices")
    def create_voice(
        name: str = Form(...),
        file: UploadFile = File(...),
        language: str = Form("th"),
        ref_text: str = Form(""),
        source: str = Form("upload"),
    ) -> Voice:
        with job(), _upload(file) as path:
            return service.clone_voice(name, path, ref_text, language, source)

    @app.patch("/api/voices/{voice_id}")
    def update_voice(voice_id: str, change: VoiceUpdate) -> Voice:
        return service.voices.update(voice_id, change)

    @app.delete("/api/voices/{voice_id}", status_code=204)
    def delete_voice(voice_id: str) -> Response:
        service.voices.delete(voice_id)
        return Response(status_code=204)

    @app.get("/api/voices/{voice_id}/audio")
    def voice_audio(voice_id: str):
        path = service.voices.ref_path(voice_id)
        if not path.is_file():
            raise KeyError(voice_id)
        return FileResponse(path, media_type="audio/wav")

    @app.post("/api/transcribe")
    def transcribe(file: UploadFile = File(...), language: str = Form("th")) -> TranscribeResult:
        with job(), _upload(file) as path:
            return service.transcribe(path, language)

    @app.post("/api/synthesize")
    def synthesize(req: SynthRequest) -> SynthResult:
        with job():
            return service.synthesize(req)

    @app.post("/api/convert")
    def convert(
        file: UploadFile = File(...),
        language: str = Form("th"),
        request: str = Form("{}"),
    ) -> SynthResult:
        try:
            fields = SynthRequest(text="x", **json.loads(request)).model_dump(exclude={"text"}, exclude_none=True)
        except (TypeError, ValueError) as e:
            raise ValueError(f"invalid request: {e}") from e
        with job(), _upload(file) as path:
            return service.convert(path, language, **fields)

    @app.get("/api/outputs")
    def list_outputs(limit: int = 100) -> list[SynthResult]:
        return service.list_outputs(limit)

    @app.get("/api/outputs/{file}")
    def get_output(file: str):
        path = _output_path(file)
        if not path.is_file():
            raise KeyError(file)
        return FileResponse(path)

    @app.delete("/api/outputs/{file}", status_code=204)
    def delete_output(file: str) -> Response:
        service.delete_output(_output_path(file).name)
        return Response(status_code=204)

    @app.get("/api/presets")
    def list_presets() -> list[Preset]:
        return list(service.settings.presets.values())

    @app.put("/api/presets/{name}")
    def put_preset(name: str, preset: Preset) -> Preset:
        if preset.name != name:
            raise ValueError("preset name does not match path")
        settings = service.settings.model_copy(deep=True)
        settings.presets[name] = preset
        service.update_settings(settings)
        return preset

    @app.delete("/api/presets/{name}", status_code=204)
    def delete_preset(name: str) -> Response:
        if name == PROTECTED_PRESET:
            raise ValueError(f"preset '{name}' cannot be deleted")
        if name not in service.settings.presets:
            raise KeyError(name)
        settings = service.settings.model_copy(deep=True)
        del settings.presets[name]
        service.update_settings(settings)
        return Response(status_code=204)

    @app.get("/api/settings")
    def get_settings() -> config.Settings:
        return service.settings

    @app.put("/api/settings")
    def put_settings(new: config.Settings, response: Response) -> config.Settings:
        if service.update_settings(new):
            response.headers["X-Restart-Required"] = "1"
        return service.settings

    @app.post("/api/heartbeat", status_code=204)
    def heartbeat() -> Response:
        lifecycle.heartbeat()
        return Response(status_code=204)

    @app.post("/api/models/unload", status_code=204)
    def unload_models() -> Response:
        service.unload_models()
        return Response(status_code=204)

    @app.post("/api/shutdown", status_code=202)
    def shutdown(background: BackgroundTasks) -> dict[str, str]:
        background.add_task(exit_fn)
        return {"status": "shutting down"}

    if static_dir is not None and static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    else:

        @app.get("/", response_class=HTMLResponse)
        def missing_static() -> str:
            return MISSING_STATIC_HTML

    return app
