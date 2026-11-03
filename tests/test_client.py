import json
import threading
import time

import httpx
import pytest

from create2tts.client import WorkerClient, WorkerError
from create2tts.models import SynthRequest

RESULT = {
    "id": "a", "file": "a.wav", "path": "/abs/a.wav", "url": "/api/outputs/a.wav",
    "duration_s": 1.0, "sample_rate": 24000, "voice": "nok", "text": "hi",
    "effects": {}, "seed": None, "created_at": "2026-11-03T10:00:00", "elapsed_s": 0.5,
}


@pytest.fixture(autouse=True)
def _tmp_data(tmp_path, monkeypatch):
    monkeypatch.setenv("CREATE2TTS_DATA", str(tmp_path))


def test_spawns_once_when_health_fails_then_succeeds():
    up = {"v": False}
    calls = []

    def handler(request):
        return httpx.Response(200 if up["v"] else 503, json={"status": "ok"})

    def spawn():
        calls.append(1)
        up["v"] = True

    WorkerClient(transport=httpx.MockTransport(handler), spawn=spawn).ensure_running(timeout_s=5)
    assert calls == [1]


def test_already_running_no_spawn():
    calls = []
    client = WorkerClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"status": "ok"})),
        spawn=lambda: calls.append(1),
    )
    client.ensure_running()
    assert calls == []


def test_concurrent_ensure_running_spawns_once():
    up = {"v": False}
    calls = []

    def spawn():
        calls.append(1)
        time.sleep(0.3)
        up["v"] = True

    transport = httpx.MockTransport(lambda r: httpx.Response(200 if up["v"] else 503, json={}))
    threads = [
        threading.Thread(target=WorkerClient(transport=transport, spawn=spawn).ensure_running, args=(5,))
        for _ in range(2)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert calls == [1]


def test_ensure_running_times_out():
    client = WorkerClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(503)), spawn=lambda: None
    )
    with pytest.raises(WorkerError):
        client.ensure_running(timeout_s=0.1)


def test_synthesize_posts_json_and_parses():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["path"] = request.url.path
        return httpx.Response(200, json=RESULT)

    client = WorkerClient(transport=httpx.MockTransport(handler))
    result = client.synthesize(SynthRequest(text="hi", softness=60))
    assert seen["path"] == "/api/synthesize"
    assert seen["body"]["text"] == "hi" and seen["body"]["softness"] == 60
    assert result.path == "/abs/a.wav"


def test_http_error_detail_becomes_worker_error():
    client = WorkerClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(400, json={"detail": "x"}))
    )
    with pytest.raises(WorkerError, match="^x$"):
        client.synthesize(SynthRequest(text="hi"))


def test_connection_failure_becomes_worker_error():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(WorkerError):
        WorkerClient(transport=httpx.MockTransport(handler)).list_voices()


def test_clone_voice_uploads_multipart(tmp_path):
    wav = tmp_path / "r.wav"
    wav.write_bytes(b"RIFF")
    seen = {}
    voice = {
        "id": "nok", "name": "nok", "language": "th", "ref_text": "x",
        "duration_s": 3.0, "created_at": "2026-11-03T10:00:00",
    }

    def handler(request):
        seen["ct"] = request.headers["content-type"]
        seen["body"] = request.content
        return httpx.Response(200, json=voice)

    result = WorkerClient(transport=httpx.MockTransport(handler)).clone_voice("nok", wav, "x")
    assert seen["ct"].startswith("multipart/form-data")
    assert b'name="ref_text"' in seen["body"]
    assert result.id == "nok"


def test_convert_sends_request_json(tmp_path):
    wav = tmp_path / "r.wav"
    wav.write_bytes(b"RIFF")
    seen = {}

    def handler(request):
        seen["body"] = request.content
        return httpx.Response(200, json={**RESULT, "transcript": "hello"})

    result = WorkerClient(transport=httpx.MockTransport(handler)).convert(
        wav, "th", voice="nok", pitch=None, softness=40
    )
    assert b'{"voice": "nok", "softness": 40}' in seen["body"]
    assert result.transcript == "hello"


def test_delete_voice_and_status_paths():
    paths = []
    status = {
        "pid": 1, "version": "0", "device": "cpu", "loaded_engines": [], "busy": False,
        "idle_s": 0.0, "auto_exit": True, "idle_timeout_min": 5.0, "web_client": False,
    }

    def handler(request):
        paths.append((request.method, request.url.path))
        return httpx.Response(200, json=status)

    client = WorkerClient(transport=httpx.MockTransport(handler))
    client.delete_voice("nok")
    assert client.status().pid == 1
    client.shutdown()
    assert paths == [
        ("DELETE", "/api/voices/nok"), ("GET", "/api/status"), ("POST", "/api/shutdown")
    ]
