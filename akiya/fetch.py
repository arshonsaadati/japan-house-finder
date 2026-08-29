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
    # akiyajapan sits behind Cloudflare, which rate-blocks rapid browser loads;
    # a generous gap between city pages keeps us under its threshold.
    "www.akiyajapan.com": 20.0,
    "akiyajapan.com": 20.0,
}
DEFAULT_DELAY = 5.0

# Domains that block non-browser agents outright (Cloudflare/UA gate); go
# straight to the real browser instead of a doomed httpx round-trip.
BROWSER_ONLY_DOMAINS = {"akiyajapan.com", "www.akiyajapan.com"}


class Client:
    def __init__(
        self,
        use_cache: bool = True,
        cache_dir: Path | None = None,
        allow_browser: bool = True,
    ):
        self.use_cache = use_cache
        self.cache_dir = cache_dir or CACHE_DIR
        self.allow_browser = allow_browser
        self._last_hit: dict[str, float] = {}
        self._browser = None  # lazily created BrowserSession
        # domains known to need the browser (seeded with always-browser sites)
        self._browser_domains: set[str] = set(BROWSER_ONLY_DOMAINS)
        self._http = httpx.Client(
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "ja,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
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

    def _browser_get(self, url: str, wait_selector: str | None = None) -> str:
        import os

        from .browser import BrowserSession

        if self._browser is None:
            # AKIYA_HEADED=1 shows the browser window; headed mode clears tough
            # WAF challenges that headless sometimes cannot.
            headless = os.environ.get("AKIYA_HEADED") not in ("1", "true", "yes")
            self._browser = BrowserSession(headless=headless).__enter__()
        self._throttle(url)
        return self._browser.get_html(url, wait_selector=wait_selector)

    def get(self, url: str, wait_selector: str | None = None) -> str:
        """Fetch URL text, via today's disk cache when enabled.

        Falls back to a real browser when the site returns a JS challenge
        (e.g. HOME'S AWS WAF), which plain HTTP cannot solve.
        """
        if "sort=" in url:
            raise ValueError(f"sorted URLs are robots-disallowed on some targets: {url}")
        from .browser import looks_blocked, looks_like_challenge

        cache = self._cache_path(url)
        if self.use_cache and cache.exists():
            cached = cache.read_text(encoding="utf-8")
            # Never trust an empty, challenge, or block page cached earlier.
            if cached.strip() and not looks_like_challenge(cached) and not looks_blocked(cached):
                return cached

        domain = urlsplit(url).netloc
        # A domain that challenged once this run keeps challenging httpx; skip
        # straight to the browser instead of paying the failed round-trip each time.
        if self.allow_browser and domain in self._browser_domains:
            text = self._browser_get(url, wait_selector=wait_selector)
            if self.use_cache and text.strip():
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                cache.write_text(text, encoding="utf-8")
            return text

        last_error: Exception | None = None
        for attempt in range(3):
            self._throttle(url)
            try:
                resp = self._http.get(url)
                if resp.status_code in (429, 503):
                    time.sleep(15 * (attempt + 1))
                    continue
                text = resp.text
                if looks_like_challenge(text, resp.status_code):
                    if self.allow_browser:
                        self._browser_domains.add(domain)
                        text = self._browser_get(url, wait_selector=wait_selector)
                    else:
                        raise RuntimeError("JS challenge and browser fallback disabled")
                else:
                    resp.raise_for_status()
                if self.use_cache and text.strip():
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    cache.write_text(text, encoding="utf-8")
                return text
            except httpx.HTTPError as e:
                last_error = e
                time.sleep(5 * (attempt + 1))
        raise RuntimeError(f"failed to fetch {url}: {last_error}")

    def close(self) -> None:
        self._http.close()
        if self._browser is not None:
            self._browser.__exit__(None, None, None)
            self._browser = None
