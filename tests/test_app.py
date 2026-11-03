from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from create2tts import config
from create2tts.models import (
    Effects,
    SynthRequest,
    SynthResult,
    TranscribeResult,
    Voice,
    VoiceUpdate,
)
from create2tts.worker.app import create_app
from create2tts.worker.lifecycle import Lifecycle


def make_voice(id="nok", name="นก"):
    return Voice(
        id=id, name=name, language="th", ref_text="สวัสดี", duration_s=3.0, created_at=datetime(2026, 1, 1)
    )


def make_result(file="a.wav", transcript=None):
    return SynthResult(
        id="a", file=file, path=f"/x/{file}", url=f"/api/outputs/{file}", duration_s=1.0, sample_rate=24000,
        voice="nok", text="hi", effects=Effects(), seed=1, created_at=datetime(2026, 1, 1),
        elapsed_s=0.1, transcript=transcript,
    )


class FakeVoices:
    def __init__(self):
        self.items = {"nok": make_voice()}

    def list(self):
        return list(self.items.values())

    def get(self, id):
        if id not in self.items:
            raise KeyError(id)
        return self.items[id]

    def ref_path(self, id):
        self.get(id)
        return config.voices_dir() / id / "ref.wav"

    def update(self, id, change: VoiceUpdate):
        voice = self.get(id).model_copy(update=change.model_dump(exclude_none=True))
        self.items[id] = voice
        return voice

    def delete(self, id):
        self.get(id)
        del self.items[id]


class FakeService:
    device = "cpu"

    def __init__(self, settings):
        self._settings = settings
        self.voices = FakeVoices()
        self.calls = []
        self.busy = False
        self.last_activity = 0.0
        self.unloaded = 0
        self.upload_seen = None
        self.fail_with = None

    @property
    def settings(self):
        return self._settings

    def _maybe_fail(self):
        if self.fail_with:
            raise self.fail_with

    def synthesize(self, req: SynthRequest):
        self._maybe_fail()
        self.calls.append(("synthesize", req))
        return make_result()

    def clone_voice(self, name, audio_path, ref_text, language, source="upload"):
        self.upload_seen = Path(audio_path)
        self.calls.append(("clone", name, ref_text, language, source, Path(audio_path).suffix))
        return make_voice("new", name)

    def transcribe(self, path, language):
        self.upload_seen = Path(path)
        return TranscribeResult(text="สวัสดี", language=language)

    def convert(self, audio_path, language, **fields):
        self.upload_seen = Path(audio_path)
        self.calls.append(("convert", language, fields))
        return make_result(transcript="สวัสดี")

    def list_outputs(self, limit=100):
        self.calls.append(("list_outputs", limit))
        return [make_result()]

    def delete_output(self, file):
        if file != "a.wav":
            raise KeyError(file)

    def delete_outputs(self, files):
        self.calls.append(("delete_outputs", files))
        return len(files)

    def clear_outputs(self):
        self.calls.append(("clear_outputs",))
        return 3

    def loaded_engines(self):
        return ["thonburian"]

    def unload_models(self):
        self.unloaded += 1

    def update_settings(self, new):
        restart = (new.host, new.port) != (self._settings.host, self._settings.port)
        self._settings = new
        return restart


class SpyLifecycle(Lifecycle):
    def __init__(self):
        super().__init__(5.0, True)
        self.events = []

    def begin_job(self):
        self.events.append("begin")
        super().begin_job()

    def end_job(self):
        self.events.append("end")
        super().end_job()


@pytest.fixture
def env(data_dir, tmp_path):
    static = tmp_path / "dist"
    static.mkdir()
    (static / "index.html").write_text("<h1>GUI</h1>", encoding="utf-8")
    service = FakeService(config.Settings())
    lifecycle = SpyLifecycle()
    exits = []
    app = create_app(service, lifecycle, static, exit_fn=lambda: exits.append(1))
    return TestClient(app), service, lifecycle, exits, static


def test_health_and_status(env):
    client, *_ = env
    health = client.get("/api/health").json()
    assert health["status"] == "ok" and "pid" in health and "version" in health
    status = client.get("/api/status").json()
    assert status["device"] == "cpu"
    assert status["loaded_engines"] == ["thonburian"]
    assert status["auto_exit"] is True
    assert status["idle_timeout_min"] == 5.0
    assert status["web_client"] is False
    client.post("/api/heartbeat")
    assert client.get("/api/status").json()["web_client"] is True


def test_heartbeat_204(env):
    client, *_ = env
    assert client.post("/api/heartbeat").status_code == 204


def test_voices_crud(env, make_wav):
    client, service, *_ = env
    assert [v["id"] for v in client.get("/api/voices").json()] == ["nok"]
    patched = client.patch("/api/voices/nok", json={"name": "นกน้อย"})
    assert patched.status_code == 200 and patched.json()["name"] == "นกน้อย"
    assert client.patch("/api/voices/zzz", json={"name": "x"}).status_code == 404
    assert client.delete("/api/voices/zzz").status_code == 404
    assert client.delete("/api/voices/nok").status_code == 204
    assert client.get("/api/voices").json() == []


def test_voice_audio(env, make_wav):
    client, service, *_ = env
    ref = service.voices.ref_path("nok")
    ref.parent.mkdir(parents=True)
    make_wav(ref, 1.0)
    response = client.get("/api/voices/nok/audio")
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert client.get("/api/voices/missing/audio").status_code == 404
    assert client.get("/api/voices/..%2F..%2Fsettings/audio").status_code == 404


def test_clone_uses_tmp_and_cleans_up(env):
    client, service, lifecycle, *_ = env
    response = client.post(
        "/api/voices",
        data={"name": "แมว", "language": "th", "source": "record"},
        files={"file": ("rec.webm", b"abc", "audio/webm")},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "แมว"
    call = service.calls[-1]
    assert call[:5] == ("clone", "แมว", "", "th", "record") and call[5] == ".webm"
    assert service.upload_seen.parent == config.tmp_dir()
    assert not service.upload_seen.exists()
    assert lifecycle.events == ["begin", "end"]


def test_transcribe(env):
    client, service, lifecycle, *_ = env
    response = client.post(
        "/api/transcribe", data={"language": "th"}, files={"file": ("a.wav", b"abc", "audio/wav")}
    )
    assert response.status_code == 200 and response.json()["text"] == "สวัสดี"
    assert not service.upload_seen.exists()
    assert lifecycle.events == ["begin", "end"]


def test_synthesize_wraps_job(env):
    client, service, lifecycle, *_ = env
    response = client.post("/api/synthesize", json={"text": "hi", "softness": 10})
    assert response.status_code == 200 and response.json()["file"] == "a.wav"
    assert service.calls[-1][1].softness == 10
    assert lifecycle.events == ["begin", "end"]


def test_synthesize_errors_map_and_end_job(env):
    client, service, lifecycle, *_ = env
    service.fail_with = ValueError("no voices")
    response = client.post("/api/synthesize", json={"text": "hi"})
    assert response.status_code == 400 and response.json()["detail"] == "no voices"
    service.fail_with = KeyError("voice")
    assert client.post("/api/synthesize", json={"text": "hi"}).status_code == 404
    assert lifecycle.events == ["begin", "end", "begin", "end"]
    assert client.post("/api/synthesize", json={"text": ""}).status_code == 422


def test_convert(env):
    client, service, lifecycle, *_ = env
    response = client.post(
        "/api/convert",
        data={"language": "th", "request": '{"voice":"nok","softness":20}'},
        files={"file": ("a.ogg", b"abc", "audio/ogg")},
    )
    assert response.status_code == 200 and response.json()["transcript"] == "สวัสดี"
    assert service.calls[-1] == ("convert", "th", {"voice": "nok", "softness": 20})
    assert not service.upload_seen.exists()
    assert lifecycle.events == ["begin", "end"]
    bad = client.post(
        "/api/convert",
        data={"language": "th", "request": "{oops"},
        files={"file": ("a.ogg", b"abc", "audio/ogg")},
    )
    assert bad.status_code == 400


def test_outputs(env, make_wav):
    client, service, *_ = env
    assert client.get("/api/outputs?limit=5").json()[0]["file"] == "a.wav"
    assert service.calls[-1] == ("list_outputs", 5)
    make_wav(config.outputs_dir() / "a.wav", 0.5)
    assert client.get("/api/outputs/a.wav").status_code == 200
    assert client.get("/api/outputs/missing.wav").status_code == 404
    assert client.delete("/api/outputs/a.wav").status_code == 204
    assert client.delete("/api/outputs/b.wav").status_code == 404


def test_bulk_delete_outputs(env):
    client, service, *_ = env
    r = client.post("/api/outputs/delete", json={"files": ["a.wav", "b.mp3"]})
    assert r.status_code == 200 and r.json() == {"deleted": 2}
    assert service.calls[-1] == ("delete_outputs", ["a.wav", "b.mp3"])
    assert client.post("/api/outputs/delete", json={"files": []}).status_code == 422
    r = client.delete("/api/outputs")
    assert r.status_code == 200 and r.json() == {"deleted": 3}
    assert service.calls[-1] == ("clear_outputs",)


def test_outputs_path_traversal_is_404(env):
    client, *_ = env
    (config.data_dir() / "settings.json").write_text("{}", encoding="utf-8")
    assert client.get("/api/outputs/..%2Fsettings.json").status_code == 404
    assert client.get("/api/outputs/%2Fetc%2Fpasswd").status_code == 404
    assert client.get("/api/outputs/..").status_code == 404
    assert client.delete("/api/outputs/..%2Fsettings.json").status_code in (404, 405)
    assert (config.data_dir() / "settings.json").exists()


def test_presets(env):
    client, service, *_ = env
    names = [p["name"] for p in client.get("/api/presets").json()]
    assert "neutral" in names
    body = {"name": "loud", "label": "ดัง", "effects": {"speed": 1.2}}
    assert client.put("/api/presets/loud", json=body).status_code == 200
    assert "loud" in service.settings.presets
    assert client.put("/api/presets/other", json=body).status_code == 400
    assert client.delete("/api/presets/loud").status_code == 204
    assert client.delete("/api/presets/loud").status_code == 404
    assert client.delete("/api/presets/neutral").status_code == 400
    assert "neutral" in service.settings.presets


def test_settings(env):
    client, service, *_ = env
    current = client.get("/api/settings").json()
    assert current["port"] == 8765
    current["nfe_step"] = 16
    response = client.put("/api/settings", json=current)
    assert response.status_code == 200
    assert "x-restart-required" not in response.headers
    assert service.settings.nfe_step == 16
    current["port"] = 9000
    response = client.put("/api/settings", json=current)
    assert response.headers["x-restart-required"] == "1"
    current["port"] = 80
    assert client.put("/api/settings", json=current).status_code == 422


def test_unload_and_shutdown(env):
    client, service, _, exits, _ = env
    assert client.post("/api/models/unload").status_code == 204
    assert service.unloaded == 1
    assert client.post("/api/shutdown").status_code == 202
    assert exits == [1]


def test_static_index(env):
    client, *_ = env
    response = client.get("/")
    assert response.status_code == 200 and "<h1>GUI</h1>" in response.text
    assert client.get("/api/health").status_code == 200


def test_missing_static_dir_shows_note(data_dir, tmp_path):
    service = FakeService(config.Settings())
    app = create_app(service, SpyLifecycle(), tmp_path / "nope", exit_fn=lambda: None)
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "npm run build" in response.text
    assert TestClient(create_app(service, SpyLifecycle(), None, exit_fn=lambda: None)).get("/").status_code == 200
