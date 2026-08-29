"""Tiny JSON API over the listing store, for the iOS swipe app.

Endpoints (stdlib only, no extra deps):
  GET /api/health              -> {"ok": true, "count": N, "updated": "..."}
  GET /api/listings            -> the store payload, plus a per-listing `photos`
                                  array: locally downloaded images served from
                                  /images/... when present, else the remote URLs.
  GET /images/<source>/<id>/<file>   static files from data/images/

Run with `uv run akiya serve --host 0.0.0.0 --port 8787` (bind 0.0.0.0 so a
phone on the same Wi-Fi / Tailscale can reach it).
"""

from __future__ import annotations

import json
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .images import IMAGES_DIR
from .sources.suumo import hires
from .store import Store


def _photos(d: dict, images_dir: Path) -> list[str]:
    urls: list[str] = []
    for p in d.get("local_images") or []:
        try:
            rel = Path(p).resolve().relative_to(images_dir.resolve())
        except ValueError:
            continue
        urls.append("/images/" + rel.as_posix())
    # Older store rows may still carry 192px SUUMO thumbnails; upgrade on the way out.
    return urls or [hires(u) for u in (d.get("image_urls") or [])]


def build_payload(store: Store, images_dir: Path = IMAGES_DIR) -> dict:
    listings = []
    for l in store.listings.values():
        d = l.to_dict()
        d["photos"] = _photos(d, images_dir)
        listings.append(d)
    listings.sort(key=lambda d: (d.get("price_yen") is None, d.get("price_yen") or 0))
    return {"count": len(listings), "listings": listings}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, store_path: Path | None, images_dir: Path, **kw):
        self.store_path = store_path
        self.images_dir = images_dir
        super().__init__(*args, directory=str(images_dir), **kw)

    def log_message(self, fmt, *args):  # quieter than the default
        print("%s - %s" % (self.address_string(), fmt % args))

    def _json(self, obj, status=HTTPStatus.OK):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/listings":
            # Re-read each request so a cron scrape shows up without a restart.
            return self._json(build_payload(Store(self.store_path), self.images_dir))
        if path == "/api/health":
            store = Store(self.store_path)
            return self._json({"ok": True, "count": len(store.listings)})
        if path.startswith("/images/"):
            self.path = path[len("/images"):]
            return super().do_GET()
        return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_HEAD(self):
        path = urlsplit(self.path).path
        if path.startswith("/images/"):
            self.path = path[len("/images"):]
            return super().do_HEAD()
        self.send_response(HTTPStatus.NOT_FOUND)
        self.end_headers()


def serve(host: str = "127.0.0.1", port: int = 8787,
          store_path: Path | None = None, images_dir: Path = IMAGES_DIR) -> None:
    images_dir.mkdir(parents=True, exist_ok=True)
    handler = partial(Handler, store_path=store_path, images_dir=images_dir)
    httpd = ThreadingHTTPServer((host, port), handler)
    print(f"akiya serve: http://{host}:{port}/api/listings  (images from {images_dir})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
