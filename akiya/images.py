"""Download listing photos for offline eyeballing and future taste-modeling.

Images land under data/images/{source}/{safe_id}/NN.ext and their paths are
recorded on the listing (local_images). Downloading is idempotent: a listing
whose folder already has files is skipped unless force=True.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .models import Listing

IMAGES_DIR = Path(__file__).resolve().parent.parent / "data" / "images"
MAX_PER_LISTING = 16  # full akiyajapan galleries run 15-16 photos

# Referer helps some hosts (HOME'S) serve images to non-browser clients.
_REFERERS = {
    "blogspot": "https://akiyabank.blogspot.com/",
    "suumo": "https://suumo.jp/",
    "homes": "https://www.homes.co.jp/",
}
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def _ext(url: str, content_type: str | None) -> str:
    if content_type:
        if "png" in content_type:
            return ".png"
        if "webp" in content_type:
            return ".webp"
        if "jpeg" in content_type or "jpg" in content_type:
            return ".jpg"
    path = urlsplit(url).path
    m = re.search(r"\.(jpg|jpeg|png|webp)$", path, re.IGNORECASE)
    return "." + m.group(1).lower() if m else ".jpg"


def download_for(listing: Listing, base_dir: Path | None = None, force: bool = False,
                 client: httpx.Client | None = None) -> list[str]:
    base_dir = base_dir or IMAGES_DIR
    folder = base_dir / listing.source / _safe(listing.source_id)
    if folder.exists() and any(folder.iterdir()) and not force:
        listing.local_images = sorted(str(p) for p in folder.iterdir() if p.is_file())
        return listing.local_images

    if not listing.image_urls:
        return []

    # A forced re-download must purge stale files first: if the corrected
    # gallery is shorter than the old one, leftover higher-index files would
    # otherwise survive and keep serving wrong photos.
    if force and folder.exists():
        for old_file in folder.iterdir():
            if old_file.is_file():
                old_file.unlink()

    own_client = client is None
    if own_client:
        client = httpx.Client(
            headers={"User-Agent": _UA, "Referer": _REFERERS.get(listing.source, "")},
            timeout=30.0, follow_redirects=True,
        )
    folder.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    try:
        for i, url in enumerate(listing.image_urls[:MAX_PER_LISTING]):
            try:
                r = client.get(url, headers={"Referer": _REFERERS.get(listing.source, "")})
                r.raise_for_status()
                path = folder / f"{i:02d}{_ext(url, r.headers.get('content-type'))}"
                path.write_bytes(r.content)
                saved.append(str(path))
            except Exception:
                continue
    finally:
        if own_client:
            client.close()
    listing.local_images = saved
    return saved


def download_all(listings: list[Listing], base_dir: Path | None = None,
                 force: bool = False) -> int:
    """Download images for many listings, sharing one HTTP client. Returns total files."""
    client = httpx.Client(headers={"User-Agent": _UA}, timeout=30.0, follow_redirects=True)
    total = 0
    try:
        for l in listings:
            total += len(download_for(l, base_dir=base_dir, force=force, client=client))
    finally:
        client.close()
    return total
