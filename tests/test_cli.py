import json

import httpx
import pytest

from create2tts import cli
from create2tts.client import WorkerClient

RESULT = {
    "id": "a", "file": "a.wav", "path": "/abs/a.wav", "url": "/api/outputs/a.wav",
    "duration_s": 1.0, "sample_rate": 24000, "voice": "nok", "text": "สวัสดี",
    "effects": {}, "seed": None, "created_at": "2026-11-03T10:00:00", "elapsed_s": 0.5,
}


@pytest.fixture(autouse=True)
def _tmp_data(tmp_path, monkeypatch):
    monkeypatch.setenv("CREATE2TTS_DATA", str(tmp_path))


def _use(monkeypatch, handler):
    monkeypatch.setattr(
        cli, "WorkerClient", lambda: WorkerClient(transport=httpx.MockTransport(handler))
    )


def test_say_sends_softness_and_prints_path(monkeypatch, capsys):
    seen = {}

    def handler(request):
        if request.url.path == "/api/health":
            return httpx.Response(200, json={"status": "ok"})
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=RESULT)

    _use(monkeypatch, handler)
    assert cli.main(["say", "สวัสดี", "--softness", "60"]) == 0
    assert seen["body"]["softness"] == 60 and seen["body"]["text"] == "สวัสดี"
    assert capsys.readouterr().out.strip() == "/abs/a.wav"


def test_worker_error_returns_1(monkeypatch, capsys):
    def handler(request):
        if request.url.path == "/api/health":
            return httpx.Response(200, json={})
        return httpx.Response(400, json={"detail": "bad voice"})

    _use(monkeypatch, handler)
    assert cli.main(["say", "x"]) == 1
    assert "bad voice" in capsys.readouterr().err


def test_status_and_stop_when_down_do_not_spawn(monkeypatch, capsys):
    _use(monkeypatch, lambda r: httpx.Response(503))
    assert cli.main(["status"]) == 0
    assert cli.main(["stop"]) == 0
    assert capsys.readouterr().out.count("not running") == 2


def test_web_opens_browser(monkeypatch):
    opened = []
    monkeypatch.setattr(cli.webbrowser, "open", opened.append)
    _use(monkeypatch, lambda r: httpx.Response(200, json={}))
    assert cli.main(["web"]) == 0
    assert opened == ["http://127.0.0.1:8765/"]
