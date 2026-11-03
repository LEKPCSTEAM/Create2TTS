import subprocess
import sys

import httpx
import pytest

from create2tts import mcp_server
from create2tts.client import WorkerClient

RESULT = {
    "id": "a", "file": "a.wav", "path": "/abs/a.wav", "url": "/api/outputs/a.wav",
    "duration_s": 1.0, "sample_rate": 24000, "voice": "nok", "text": "hi",
    "effects": {}, "seed": None, "created_at": "2026-11-03T10:00:00", "elapsed_s": 0.5,
}


@pytest.fixture(autouse=True)
def _tmp_data(tmp_path, monkeypatch):
    monkeypatch.setenv("CREATE2TTS_DATA", str(tmp_path))


def _use(monkeypatch, handler, spawn=None):
    spawned = []
    client = WorkerClient(
        transport=httpx.MockTransport(handler), spawn=spawn or (lambda: spawned.append(1))
    )
    monkeypatch.setattr(mcp_server, "_client", lambda: client)
    return spawned


def test_import_leaves_torch_out():
    code = "import sys, create2tts.mcp_server, create2tts.cli; print('torch' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


def test_synthesize_returns_path(monkeypatch):
    def handler(request):
        if request.url.path == "/api/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(200, json=RESULT)

    _use(monkeypatch, handler)
    assert mcp_server.synthesize("hi", softness=60)["path"] == "/abs/a.wav"


def test_status_when_down_does_not_spawn(monkeypatch):
    spawned = _use(monkeypatch, lambda r: httpx.Response(503))
    assert mcp_server.tts_status() == {"running": False}
    assert mcp_server.free_memory() == {"running": False}
    assert spawned == []


def test_open_gui_opens_browser(monkeypatch):
    opened = []
    monkeypatch.setattr(mcp_server.webbrowser, "open", opened.append)
    _use(monkeypatch, lambda r: httpx.Response(200, json={}))
    assert mcp_server.open_gui() == "http://127.0.0.1:8765/"
    assert opened == ["http://127.0.0.1:8765/"]


def test_tool_names_and_descriptions():
    import asyncio

    tools = {t.name: t for t in asyncio.run(mcp_server.mcp.list_tools())}
    assert set(tools) == {
        "list_voices", "list_presets", "synthesize", "clone_voice", "convert_voice",
        "delete_voice", "open_gui", "tts_status", "free_memory",
    }
    assert "absolute" in tools["synthesize"].description
    assert "0.5-2.0" in tools["synthesize"].description
