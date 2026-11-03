import webbrowser
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from .client import WorkerClient
from .models import SynthRequest

mcp = MCPServer("create2tts")


def _client() -> WorkerClient:
    return WorkerClient()


def _ready() -> WorkerClient:
    client = _client()
    client.ensure_running()
    return client


@mcp.tool()
def list_voices() -> list[dict]:
    """List saved voices (id, name, language, ref_text). Use an id as `voice` in synthesize."""
    return [v.model_dump(mode="json") for v in _ready().list_voices()]


@mcp.tool()
def list_presets() -> list[dict]:
    """List effect presets (name, label, effects). Use a name as `preset` in synthesize."""
    return [p.model_dump(mode="json") for p in _ready().list_presets()]


@mcp.tool()
def synthesize(
    text: str,
    voice: str | None = None,
    preset: str | None = None,
    speed: float | None = None,
    pitch: float | None = None,
    softness: int | None = None,
    warmth: int | None = None,
    seed: int | None = None,
    format: str | None = None,
) -> dict:
    """Generate Thai or English speech from text and save an audio file.

    Returns a dict whose `path` is the absolute path of the audio file.
    text: 1-5000 chars, language is auto-detected.
    voice: voice id from list_voices (default voice if omitted).
    preset: preset name from list_presets; the fields below override it.
    speed: 0.5-2.0, 1.0 is normal.
    pitch: -6 to 6 semitones.
    softness: 0-100, higher is gentler and less sharp.
    warmth: -100 to 100, positive is warmer, negative is brighter.
    seed: integer for reproducible output.
    format: "wav" or "mp3".
    """
    req = SynthRequest(
        text=text, voice=voice, preset=preset, speed=speed, pitch=pitch,
        softness=softness, warmth=warmth, seed=seed, format=format,
    )
    return _ready().synthesize(req).model_dump(mode="json")


@mcp.tool()
def clone_voice(name: str, audio_path: str, ref_text: str | None = None, language: str = "th") -> dict:
    """Save a new voice from a 2-15 s reference clip (absolute path, any audio format).

    ref_text: exact transcript of the clip; transcribed automatically if omitted.
    language: "th" or "en".
    """
    return _ready().clone_voice(name, Path(audio_path), ref_text, language).model_dump(mode="json")


@mcp.tool()
def convert_voice(
    audio_path: str,
    voice: str | None = None,
    language: str = "th",
    preset: str | None = None,
    speed: float | None = None,
    pitch: float | None = None,
    softness: int | None = None,
    warmth: int | None = None,
) -> dict:
    """Transcribe an audio file and re-speak it in a saved voice.

    Returns a dict whose `path` is the absolute path of the new audio file.
    audio_path: absolute path of the source audio. language: "th" or "en".
    speed 0.5-2.0, pitch -6..6 semitones, softness 0-100, warmth -100..100.
    """
    return _ready().convert(
        Path(audio_path), language, voice=voice, preset=preset, speed=speed,
        pitch=pitch, softness=softness, warmth=warmth,
    ).model_dump(mode="json")


@mcp.tool()
def delete_voice(voice: str) -> dict:
    """Delete a saved voice by id."""
    _ready().delete_voice(voice)
    return {"deleted": voice}


@mcp.tool()
def open_gui() -> str:
    """Open the web GUI in the default browser and return its URL."""
    client = _ready()
    url = f"{client.base_url}/"
    webbrowser.open(url)
    return url


@mcp.tool()
def tts_status() -> dict:
    """Report whether the worker is running, with loaded models and idle time. Never starts it."""
    client = _client()
    if not client.is_running():
        return {"running": False}
    return {"running": True, **client.status().model_dump(mode="json")}


@mcp.tool()
def free_memory() -> dict:
    """Shut the worker down to free model memory. It restarts on the next call."""
    client = _client()
    if not client.is_running():
        return {"running": False}
    client.shutdown()
    return {"running": False, "stopped": True}


def main() -> None:
    mcp.run("stdio")
