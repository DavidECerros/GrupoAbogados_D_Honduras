"""Production launcher: one process, local disk, no development server."""

import argparse
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description="Grupo Abogados D Honduras")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--cert")
    parser.add_argument("--key")
    parser.add_argument("--allowed-hosts")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not (ROOT / "frontend" / "dist" / "index.html").is_file():
        parser.error("Compile la interfaz con npm run build o use el paquete de ejecución.")
    if args.lan:
        if not args.cert or not args.key or not args.allowed_hosts:
            parser.error(
                "LAN requiere --cert, --key y --allowed-hosts; no se habilita HTTP en LAN."
            )
        os.environ["GESTOR_HTTPS"] = "1"
        os.environ["GESTOR_ALLOWED_HOSTS"] = args.allowed_hosts
        args.host = "0.0.0.0"
    elif args.host not in ("127.0.0.1", "::1"):
        parser.error("El modo local escucha únicamente en loopback. Use --lan con HTTPS.")
    os.chdir(ROOT)
    import uvicorn

    url = f"{'https' if args.lan else 'http'}://localhost:{args.port}"
    if not args.no_browser:

        def open_browser():
            time.sleep(1.5)
            webbrowser.open(url)

        threading.Thread(target=open_browser, daemon=True).start()
    print(
        f"Grupo Abogados D Honduras: {url}\nPara cerrar de forma controlada, pulse Ctrl+C en esta ventana."
    )
    uvicorn.run(
        "backend.app:app",
        host=args.host,
        port=args.port,
        workers=1,
        ssl_certfile=args.cert,
        ssl_keyfile=args.key,
        log_level="warning",
        access_log=False,
    )


if __name__ == "__main__":
    main()
