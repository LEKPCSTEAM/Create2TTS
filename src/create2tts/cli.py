import argparse
import json
import sys
import webbrowser
from pathlib import Path

from .client import WorkerClient, WorkerError
from .config import load_settings
from .models import SynthRequest


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tts")
    sub = p.add_subparsers(dest="cmd", required=True)

    serve = sub.add_parser("serve")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    serve.add_argument("--auto-exit", action="store_true")

    sub.add_parser("web")

    say = sub.add_parser("say")
    say.add_argument("text")
    say.add_argument("--voice")
    say.add_argument("--preset")
    say.add_argument("--speed", type=float)
    say.add_argument("--pitch", type=float)
    say.add_argument("--softness", type=int)
    say.add_argument("--warmth", type=int)
    say.add_argument("--seed", type=int)
    say.add_argument("--format", choices=["wav", "mp3"])

    sub.add_parser("voices")

    clone = sub.add_parser("clone")
    clone.add_argument("name")
    clone.add_argument("file", type=Path)
    clone.add_argument("--text")
    clone.add_argument("--lang", choices=["th", "en"], default="th")

    sub.add_parser("status")
    sub.add_parser("stop")
    sub.add_parser("mcp")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return _run(args)
    except (WorkerError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def _run(args: argparse.Namespace) -> int:
    if args.cmd == "serve":
        from .worker.server import run

        settings = load_settings()
        run(args.host or settings.host, args.port or settings.port, args.auto_exit)
        return 0
    if args.cmd == "mcp":
        from .mcp_server import main as mcp_main

        mcp_main()
        return 0

    client = WorkerClient()
    if args.cmd == "stop":
        if client.is_running():
            client.shutdown()
        else:
            print("worker is not running")
        return 0
    if args.cmd == "status":
        if not client.is_running():
            print("worker is not running")
            return 0
        print(client.status().model_dump_json(indent=2))
        return 0

    client.ensure_running()
    if args.cmd == "web":
        webbrowser.open(f"{client.base_url}/")
    elif args.cmd == "say":
        fields = {k: getattr(args, k) for k in ("voice", "preset", "speed", "pitch", "softness", "warmth", "seed", "format")}
        print(client.synthesize(SynthRequest(text=args.text, **fields)).path)
    elif args.cmd == "voices":
        for v in client.list_voices():
            print(f"{v.id}\t{v.name}\t{v.language}\t{v.duration_s:.1f}s")
    elif args.cmd == "clone":
        voice = client.clone_voice(args.name, args.file, args.text, args.lang)
        print(json.dumps({"id": voice.id, "name": voice.name}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
