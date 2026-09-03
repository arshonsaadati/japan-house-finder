"""Tiny JSON API over the listing store, for the iOS swipe app.

Endpoints (stdlib only, no extra deps):
  GET /api/health              -> {"ok": true, "count": N, "updated": "..."}
  GET /api/listings            -> the store payload, plus a per-listing `photos`
                                  array: locally downloaded images served from
                                  /images/... when present, else the remote URLs.
  GET /images/<source>/<id>/<file>   static files from data/images/

Auth: if AKIYA_API_TOKEN is set (it always is in production), every request
must carry it — `Authorization: Bearer <token>` or `?token=<token>` (the latter
for photo URLs, which the app loads without custom headers). Anything else is
a bare 401. Compared in constant time.

Run with `uv run akiya serve` behind `tailscale serve`/`funnel`, or bind
`--host 0.0.0.0` on a trusted LAN.
"""

from __future__ import annotations

import hmac
import json
import os
import random
from datetime import date
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from datetime import datetime, timezone
from pathlib import Path as _P
from threading import Lock

from .images import IMAGES_DIR
from .sources.suumo import hires
from .store import Store


LIKES_PATH = _P(__file__).resolve().parent.parent / "data" / "likes.json"
_likes_lock = Lock()
MAX_LIKES_BODY = 256 * 1024  # plenty for a few users; refuses junk


def load_likes(path: Path = LIKES_PATH) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def upsert_likes(device: str, name: str, likes: list[str], path: Path = LIKES_PATH) -> dict:
    """Replace one device's like list. Returns the full map {device: {...}}."""
    with _likes_lock:
        data = load_likes(path)
        data[device] = {
            "name": (name or "?")[:40],
            "likes": [str(k)[:200] for k in likes][:2000],
            "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
        return data


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


def build_payload(store: Store, images_dir: Path = IMAGES_DIR,
                  order: str = "random") -> dict:
    listings = []
    for l in store.listings.values():
        d = l.to_dict()
        d["photos"] = _photos(d, images_dir)
        listings.append(d)
    if order == "price":
        listings.sort(key=lambda d: (d.get("price_yen") is None, d.get("price_yen") or 0))
    else:
        # Random deck for the swipe app, but seeded by the day so refreshes
        # and pagination inside one session keep a stable order (no repeats,
        # no mid-swipe reshuffles). ?sort=price restores the old order.
        listings.sort(key=lambda d: f"{d.get('source')}:{d.get('source_id')}")
        random.Random(date.today().isoformat()).shuffle(listings)
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

    def _authorized(self) -> bool:
        token = os.environ.get("AKIYA_API_TOKEN", "")
        if not token:
            return True  # dev mode, no token configured
        hdr = self.headers.get("Authorization", "")
        presented = hdr[7:] if hdr.startswith("Bearer ") else ""
        if not presented:
            qs = parse_qs(urlsplit(self.path).query)
            presented = (qs.get("token") or [""])[0]
        return hmac.compare_digest(presented, token)

    def do_GET(self):
        if not self._authorized():
            return self._json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        path = urlsplit(self.path).path
        if path == "/api/listings":
            # Re-read each request so a cron scrape shows up without a restart.
            qs = parse_qs(urlsplit(self.path).query)
            order = (qs.get("sort") or ["random"])[0]
            return self._json(build_payload(Store(self.store_path), self.images_dir, order=order))
        if path == "/api/health":
            store = Store(self.store_path)
            return self._json({"ok": True, "count": len(store.listings)})
        if path == "/api/likes":
            return self._json(load_likes())
        if path.startswith("/images/"):
            self.path = path[len("/images"):]
            return super().do_GET()
        return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
        if not self._authorized():
            return self._json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        path = urlsplit(self.path).path
        if path != "/api/likes":
            return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        try:
            n = int(self.headers.get("Content-Length", 0))
            if not 0 < n <= MAX_LIKES_BODY:
                raise ValueError("bad length")
            body = json.loads(self.rfile.read(n))
            device = str(body["device"])[:64]
            name = str(body.get("name", ""))
            likes = list(body.get("likes", []))
        except (ValueError, KeyError, TypeError) as e:
            return self._json({"error": f"bad request: {e}"}, HTTPStatus.BAD_REQUEST)
        return self._json(upsert_likes(device, name, likes))

    def do_HEAD(self):
        if not self._authorized():
            self.send_response(HTTPStatus.UNAUTHORIZED)
            self.end_headers()
            return
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
    auth = "token required" if os.environ.get("AKIYA_API_TOKEN") else "NO TOKEN (dev mode)"
    print(f"akiya serve: http://{host}:{port}/api/listings  (images from {images_dir}; {auth})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
