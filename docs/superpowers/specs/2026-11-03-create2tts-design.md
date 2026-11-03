# Create2TTS — Design

Local, free Thai + English TTS with voice cloning, tone/softness control, a web GUI (use + settings) and an MCP server. No auth. Personal/internal use (CC-BY-NC weights allowed). Target machine: Apple M4 Pro, 24 GB, macOS.

## Decisions

- Thai engine: ThonburianTTS megaF5 checkpoint loaded through `f5_tts.api.F5TTS(model="F5TTS_Base")` (the `thonburian-tts` wheel ships no code). English engine: `F5TTS_v1_Base` default checkpoint. Same adapter for both.
- The engine is chosen by the **voice's language**, not the text. A Thai voice reads mixed text best-effort.
- Device: `auto` → `mps` if available else `cpu`. Set `PYTORCH_ENABLE_MPS_FALLBACK=1`.
- Reference transcription: HF `transformers` Whisper pipeline on the same device. Thai → `biodatlab/whisper-th-large-v3-combined`, English → `openai/whisper-large-v3-turbo`. Loaded per call, freed after.
- "Convert a recording" v1 = transcribe the recording, then synthesize the transcript with the chosen voice. True voice conversion (Seed-VC) is out of scope for v1.
- Resource policy: nothing is resident until used. The worker starts on demand and exits after `idle_timeout_min` with no job and no open GUI tab.

## Architecture

```
Claude Code ──stdio──▶ tts-mcp (no torch import) ──HTTP──┐
tts CLI ─────────────────────────────────────────HTTP──┤
Browser (GUI, heartbeat every 30 s) ─────────────HTTP──┤
                                                        ▼
            tts-worker  FastAPI on settings.host:settings.port (127.0.0.1:8765)
            REST /api/* + static GUI from web/dist
            TTSService: normalize → split → engine → concat → effects → file
            Lifecycle watchdog (5 s tick): idle → unload models / exit
```

`WorkerClient.ensure_running()` spawns `python -m create2tts.cli serve --auto-exit` detached when `/api/health` does not answer, guarded by an `fcntl` lock on `data/worker.lock`, logging to `data/worker.log`.

## Data layout (`data/`, override with env `CREATE2TTS_DATA`)

- `settings.json` — `config.Settings` (see `src/create2tts/config.py`).
- `voices/<id>/ref.wav` (24 kHz mono float, edge-trimmed, 2–15 s) + `voices/<id>/meta.json` (`models.Voice`).
- `outputs/<YYYYMMDD-HHMMSS>-<6 hex>.<wav|mp3>` + sidecar `<same stem>.json` (`models.SynthResult`).
- `tmp/` scratch uploads. `worker.log`, `worker.lock`.

Voice id = slug of `pythainlp.transliterate.romanize(name)` (lowercase `[a-z0-9-]`), `voice` if empty, `-2`, `-3`… if taken. Must match `^[a-z0-9_-]{1,48}$`.

## Effects (`models.Effects`)

Preset merge: start from `settings.presets[req.preset or settings.default_preset].effects`, then every non-None field of the request overrides. Unknown preset → `ValueError`.

- `speed` 0.5–2.0 → passed to the model (keeps pitch).
- `pitch` −6…+6 semitones → `pedalboard.PitchShift` when |pitch| ≥ 0.05.
- `warmth` w ∈ −100…100 → `LowShelfFilter(cutoff 250 Hz, gain 6·w/100 dB)` + `HighShelfFilter(cutoff 6000 Hz, gain −3·w/100 dB)` when w ≠ 0.
- `softness` s = softness/100, when s > 0 → `HighShelfFilter(5000 Hz, −9·s dB)`, `LowpassFilter(16000 − 8000·s Hz)`, `Compressor(threshold −18 − 6·s dB, ratio 1 + 2·s, attack 10 ms, release 120 ms)`.
- Always last: peak-normalize to 0.89 (≈ −1 dBFS) when peak > 0. All-zero input stays zero (no NaN).

Built-in presets live in `config._default_presets()`; users add/edit/delete presets from the GUI (stored in `settings.presets`). `neutral` cannot be deleted.

## Text processing

- `detect_language`: Thai chars (U+0E00–U+0E7F) ≥ 20 % of Thai+Latin letters → `th`, else `en`; no letters → `th`.
- `normalize_text(text, lang)`: drop markdown markers (`*`, `#`, `` ` ``, `>` at line start), collapse spaces, keep single newlines. Thai only: numbers to words (`1,250` → `หนึ่งพันสองร้อยห้าสิบ`, `3.5` → `สามจุดห้า`, decimals read digit by digit), `%` → `เปอร์เซ็นต์`, `฿100` → `หนึ่งร้อยบาท`, `ๆ` repeats the previous word (`ดีๆ` → `ดีดี`).
- `split_segments(text, lang, max_chars)`: lines → sentences (Thai `pythainlp.tokenize.sent_tokenize`, English split after `.!?`+space) → merge pieces < 8 chars into the previous → split pieces > `max_chars` at the last space (Thai: last word boundary) before the limit. No empty strings.
- Segments are synthesized separately and joined with `chunk_gap_ms` silence and 6 ms edge fades.

## REST API (worker)

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/api/health` | — | `{"status":"ok","version","pid"}` |
| GET | `/api/status` | — | `WorkerStatus` |
| GET | `/api/voices` | — | `Voice[]` |
| POST | `/api/voices` | multipart `name`, `file`, `language` (default `th`), `ref_text?`, `source?` | `Voice` (transcribes when `ref_text` empty) |
| PATCH | `/api/voices/{id}` | `VoiceUpdate` | `Voice` |
| DELETE | `/api/voices/{id}` | — | 204 |
| GET | `/api/voices/{id}/audio` | — | `audio/wav` |
| POST | `/api/transcribe` | multipart `file`, `language` | `TranscribeResult` |
| POST | `/api/synthesize` | `SynthRequest` | `SynthResult` |
| POST | `/api/convert` | multipart `file`, `language`, `request` (JSON of `SynthRequest` fields minus `text`) | `SynthResult` with `transcript` |
| GET | `/api/outputs?limit=100` | — | `SynthResult[]` newest first |
| GET / DELETE | `/api/outputs/{file}` | — | audio / 204 |
| GET | `/api/presets` | — | `Preset[]` |
| PUT / DELETE | `/api/presets/{name}` | `Preset` | `Preset` / 204 |
| GET / PUT | `/api/settings` | `Settings` | `Settings` (PUT also returns header `X-Restart-Required: 1` when host/port changed) |
| POST | `/api/heartbeat` | — | 204 |
| POST | `/api/models/unload` | — | 204 |
| POST | `/api/shutdown` | — | 202, process exits after responding |

Errors: unknown id → 404, `ValueError`/validation → 400/422 with `{"detail": "..."}`. `{file}` must match `^[\w.-]+$` and resolve inside `outputs/`.

## MCP tools (stdio, `mcp.server.fastmcp.FastMCP("create2tts")`)

`list_voices`, `list_presets`, `synthesize(text, voice?, preset?, speed?, pitch?, softness?, warmth?, seed?, format?)` → `SynthResult` (agents use `path`), `clone_voice(name, audio_path, ref_text?, language="th")`, `convert_voice(audio_path, voice?, language="th", preset?, speed?, pitch?, softness?, warmth?)`, `delete_voice(voice)`, `open_gui()` → URL (opens browser), `tts_status()`, `free_memory()` (shuts the worker down). Every tool calls `ensure_running()` first except `tts_status`/`free_memory`, which report "not running" instead of starting it.

## CLI (`tts`)

`serve [--host] [--port] [--auto-exit]`, `web` (ensure worker + open browser), `say TEXT [--voice --preset --speed --pitch --softness --warmth --seed --format]` (prints output path), `voices`, `clone NAME FILE [--text] [--lang th|en]`, `status`, `stop`, `mcp`.

## Lifecycle

- `idle_s` = time since the last job ended (or worker start).
- Web client active = heartbeat within the last 90 s.
- Each tick, when no job is running and `idle_s ≥ idle_timeout_min·60`: if `auto_exit` and no web client → exit; otherwise unload models (once).
- `idle_timeout_min = 0` → the condition holds right after a job ends.

## GUI (Thai labels, Vite + React 18 + TS, served from `web/dist`)

Tabs: **สร้างเสียง** (text + char count, voice, preset chips, sliders speed/pitch/softness/warmth, seed with lock, generate, player + download, save current sliders as preset), **คลังเสียง** (list, play ref, edit name/ref_text/language, delete, add voice by upload or browser recording → auto-transcribe → edit → save), **แปลงเสียง** (upload/record → transcribe → edit → voice + effects → generate), **ประวัติ** (outputs with player, params, download, delete), **ตั้งค่า** (all `Settings` fields grouped: Server, Model, Output, Advanced, preset manager; worker status panel with loaded models, device, idle timer, buttons "ปล่อยหน่วยความจำ" and "ปิด worker"). Shows "กำลังโหลดโมเดล…" while the first synthesis runs. Sends `POST /api/heartbeat` every 30 s.

## Out of scope (v1)

Auth, LAN exposure by default, streaming audio, true voice conversion, training/fine-tuning, a Windows/Linux GPU path.
