"""Polite HTTP client: per-domain throttle, retries, on-disk cache.

The cache key includes the date so a normal daily run refreshes, but
repeated dev iterations the same day never re-hit the sites.
"""

from __future__ import annotations

import hashlib
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import httpx

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"

# HOME'S (CloudFront) and SUUMO (AWS WAF) 403 a custom UA string even though
# their robots.txt permits the paths we read. A mainstream browser UA is
# required to reach the pages at all. We stay polite instead via low volume,
# per-domain throttling, and aggressive disk caching. See DECISIONS.md.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)

# Seconds between requests to the same domain. SUUMO gets the bingbot
# crawl-delay from its robots.txt applied to us voluntarily.
DOMAIN_DELAYS = {
    "suumo.jp": 30.0,
    "www.homes.co.jp": 5.0,
    "akiyabank.blogspot.com": 2.0,
}
DEFAULT_DELAY = 5.0


class Client:
    def __init__(self, use_cache: bool = True, cache_dir: Path | None = None):
        self.use_cache = use_cache
        self.cache_dir = cache_dir or CACHE_DIR
        self._last_hit: dict[str, float] = {}
        self._http = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "ja,en;q=0.8"},
            timeout=30.0,
            follow_redirects=True,
        )

    def _cache_path(self, url: str) -> Path:
        h = hashlib.sha256(url.encode()).hexdigest()[:24]
        return self.cache_dir / f"{date.today().isoformat()}-{h}.body"

    def _throttle(self, url: str) -> None:
        domain = urlsplit(url).netloc
        delay = DOMAIN_DELAYS.get(domain, DEFAULT_DELAY)
        last = self._last_hit.get(domain)
        if last is not None:
            wait = delay - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
        self._last_hit[domain] = time.monotonic()

    def get(self, url: str) -> str:
        """Fetch URL text, via today's disk cache when enabled."""
        if "sort=" in url:
            raise ValueError(f"sorted URLs are robots-disallowed on some targets: {url}")
        cache = self._cache_path(url)
        if self.use_cache and cache.exists():
            return cache.read_text(encoding="utf-8")

        last_error: Exception | None = None
        for attempt in range(3):
            self._throttle(url)
            try:
                resp = self._http.get(url)
                if resp.status_code in (429, 503):
                    time.sleep(15 * (attempt + 1))
                    continue
                resp.raise_for_status()
                text = resp.text
                if self.use_cache:
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    cache.write_text(text, encoding="utf-8")
                return text
            except httpx.HTTPError as e:
                last_error = e
                time.sleep(5 * (attempt + 1))
        raise RuntimeError(f"failed to fetch {url}: {last_error}")

    def close(self) -> None:
        self._http.close()
