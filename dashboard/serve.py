#!/usr/bin/env python3
"""Local preview server for the dashboard.

    python3 dashboard/serve.py [port]      # default 8099

Plain `http.server` lets the browser cache assets, so edits to app.js or the
stylesheets appear only after a hard reload — which silently wastes time when
checking a layout change. This sends no-store on everything.

Production is Caddy (see caddy/Caddyfile); this is development only.
"""

from __future__ import annotations

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:  # quieter output
        if "GET" in (fmt % args) and " 200 " not in (fmt % args):
            super().log_message(fmt, *args)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
    handler = partial(NoCacheHandler, directory=str(ROOT))
    print(f"dashboard: http://localhost:{port}  (pin a view with ?view=nas)")
    ThreadingHTTPServer(("0.0.0.0", port), handler).serve_forever()


if __name__ == "__main__":
    main()
