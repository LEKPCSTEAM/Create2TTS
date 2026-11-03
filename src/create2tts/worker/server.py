import threading
import time

from ..device import enable_mps_fallback

WATCHDOG_TICK_S = 5


def run(host: str | None = None, port: int | None = None, auto_exit: bool = False) -> None:
    enable_mps_fallback()
    import uvicorn

    from ..asr import Transcriber
    from ..config import PROJECT_ROOT, load_settings, outputs_dir, voices_dir
    from ..device import resolve_device
    from ..engines.f5 import F5Engine
    from ..service import TTSService
    from ..voices import VoiceLibrary
    from .app import create_app
    from .lifecycle import Lifecycle

    settings = load_settings()
    device = resolve_device(settings.device)
    service = TTSService(
        settings,
        VoiceLibrary(voices_dir()),
        F5Engine,
        Transcriber(settings, device),
        outputs_dir(),
        device,
    )
    lifecycle = Lifecycle(settings.idle_timeout_min, auto_exit)
    config = uvicorn.Config(
        None,
        host=host or settings.host,
        port=port or settings.port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    def exit_fn() -> None:
        server.should_exit = True

    config.app = create_app(service, lifecycle, PROJECT_ROOT / "web" / "dist", exit_fn=exit_fn)

    def watchdog() -> None:
        while not server.should_exit:
            time.sleep(WATCHDOG_TICK_S)
            lifecycle.idle_timeout_min = service.settings.idle_timeout_min
            action = lifecycle.tick(service, exit_fn)
            if action != "none":
                print(f"[worker] idle -> {action}", flush=True)

    threading.Thread(target=watchdog, daemon=True).start()
    print(f"[worker] device={device} auto_exit={auto_exit} http://{config.host}:{config.port}/", flush=True)
    server.run()
