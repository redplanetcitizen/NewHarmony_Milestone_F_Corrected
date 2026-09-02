from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def serve(directory: Path, port: int = 8765) -> None:
    directory = directory.resolve()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

    url = f"http://127.0.0.1:{port}"
    print(f"Cruscotto disponibile su {url}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()

