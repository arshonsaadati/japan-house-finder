"""Playwright-based fetcher for pages behind JS challenges or logins.

Used for:
- HOME'S pages that intermittently return an AWS WAF JS challenge (HTTP 202),
  which plain HTTP cannot solve but a real browser clears automatically.
- akiyajapan.com, which blocks non-browser agents and needs a logged-in
  session (credentials from env, never committed).

Kept lazy so importing the package doesn't require Playwright's browser to be
installed unless a browser fetch is actually needed.
"""

from __future__ import annotations

import os

CHALLENGE_MARKERS = ("awswaf", "challenge.js", "Just a moment", "cf-browser-verification")
# Text that appears on the rendered challenge interstitial itself.
CHALLENGE_BODY_MARKERS = ("confirm you are human", "確認しています", "Checking your browser")


def looks_like_challenge(text: str, status: int | None = None) -> bool:
    if status == 202:
        return True
    if not text:
        return False
    if len(text) < 3000 and any(m in text for m in CHALLENGE_MARKERS):
        return True
    return any(m.lower() in text.lower() for m in CHALLENGE_BODY_MARKERS)


class ChallengeUnsolved(RuntimeError):
    pass


class BrowserSession:
    """A single reusable Playwright browser context.

    Use as a context manager. `headless=False` shows the window (useful for
    akiyajapan login and for letting WAF challenges solve visibly).
    """

    def __init__(self, headless: bool = True, storage_state: str | None = None):
        self.headless = headless
        self.storage_state = storage_state
        self._pw = None
        self._browser = None
        self._context = None

    def __enter__(self) -> "BrowserSession":
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        # Anti-automation-detection: AWS WAF/Cloudflare fingerprint headless
        # Chrome and hand it harder (sometimes unsolvable) challenges. These
        # args + the init script below make it look like an ordinary browser.
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        ctx_kwargs = {
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
            ),
            "locale": "ja-JP",
            "timezone_id": "Asia/Tokyo",
            "viewport": {"width": 1400, "height": 1000},
        }
        if self.storage_state and os.path.exists(self.storage_state):
            ctx_kwargs["storage_state"] = self.storage_state
        self._context = self._browser.new_context(**ctx_kwargs)
        self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        return self

    def __exit__(self, *exc) -> None:
        if self.storage_state and self._context:
            try:
                self._context.storage_state(path=self.storage_state)
            except Exception:
                pass
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def get_html(
        self,
        url: str,
        wait_selector: str | None = None,
        challenge_timeout_ms: int = 50_000,
    ) -> str:
        """Navigate to url and return the settled HTML.

        Actively waits for an AWS WAF / Cloudflare JS challenge to solve (the
        script POSTs a token and reloads into the real page). Raises
        ChallengeUnsolved if the interstitial never clears, so a challenge
        page is never mistaken for content or cached.
        """
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)

            deadline = challenge_timeout_ms
            waited = 0
            step = 1000
            while waited < deadline:
                content = page.content()
                if not looks_like_challenge(content):
                    break
                page.wait_for_timeout(step)
                waited += step
            else:
                raise ChallengeUnsolved(f"WAF challenge did not clear for {url}")

            # Prefer the specific content signal; fall back to a short
            # networkidle. Ad/tracker-heavy pages never truly go idle, so a
            # long networkidle wait just burns the full timeout on every page.
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=12_000)
                except Exception:
                    pass
            else:
                try:
                    page.wait_for_load_state("networkidle", timeout=4_000)
                except Exception:
                    pass

            content = page.content()
            if looks_like_challenge(content):
                raise ChallengeUnsolved(f"WAF challenge still present for {url}")
            return content
        finally:
            page.close()
