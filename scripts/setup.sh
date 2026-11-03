#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

command -v uv >/dev/null || { echo "uv not found: https://docs.astral.sh/uv/"; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg not found: brew install ffmpeg"; exit 1; }
command -v npm >/dev/null || { echo "npm not found: install Node.js 20+"; exit 1; }

uv sync
(cd web && npm install && npm run build)

echo
echo "Done. Open the GUI:   uv run tts web"
echo "Add to Claude Code:   claude mcp add tts -- uv run --directory \"$PWD\" tts-mcp"
