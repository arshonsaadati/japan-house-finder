# Engineering decisions log

Running record of non-obvious choices made while building the toolkit, so a
future session (or teammate) understands *why*, not just *what*.

## 2026-08-29 — Initial build

### Sources: which sites, which access method
- **akiyabank.blogspot.com** — via the Blogspot JSON feed
  (`/feeds/posts/default?alt=json&max-results=500`), one request for the whole
  corpus. robots.txt disallows `/search` (label/pagination pages) but not
  feeds. Fields are labeled plain text inside the post HTML → strip tags, regex
  the `登録#/住所/価格/土地/建物/その他` labels. Only ~3 listings are live at any
  time (123/127 are 成約済 sold); still the best *Shiribeshi-specific* source and
  great for price history.
- **homes.co.jp/akiyabank** (LIFULL HOME'S) — plain HTTP + BeautifulSoup.
  robots.txt permits `/akiyabank/`. List cards are sparse (type, address,
  price); real specs (間取り, 築年月, 建物構造, zoning, parking) require the detail
  page `/akiyabank/b-{id}/`, which exposes them as clean `th/td` pairs. City
  slugs are gun+town (e.g. `yoichi_yoichi`, `isoya_rankoshi`), discovered from
  the prefecture index rather than guessed.
- **suumo.jp** — plain HTTP. Richest source: every field
  (price/address/station/land+building m²/layout/build year+month) is on the
  results page in `div.property_unit` dt/dd pairs, 20 per page. Constraints
  encoded in code: never build `sort=` URLs (robots-disallowed → `fetch.get`
  raises on them), ≥30s per-request throttle (mirrors their bingbot
  crawl-delay), disk cache so dev never re-hits.
- **akiyajapan.com** — deferred to a Playwright path (see below). robots.txt
  bans AI-agent UAs, 403s at the edge, and runs a documented scraper honeypot,
  so no plain-HTTP scraper. The user has a real account and wants it; we drive
  a real (non-headless) logged-in browser at low volume instead.

### Browser User-Agent for HOME'S / SUUMO
Both sit behind CloudFront / AWS WAF and return **403 to a custom UA string**
even on robots-permitted paths. A mainstream browser UA is required to load the
page at all. Decision: send a Chrome UA, and be a good citizen through *behavior*
instead — low request volume (target cities only), per-domain throttle, and a
date-keyed disk cache so repeated runs the same day never re-fetch. robots.txt
(the actual machine-readable access policy) permits these paths.

### Caching keyed by date
`data/cache/{YYYY-MM-DD}-{hash}.body`. A normal daily run refreshes once/day;
repeated dev iterations the same day are free and site-friendly. `--no-cache`
bypasses it. Cache dir is gitignored.

### Secrets
akiyajapan.com credentials are **never** written to a repo file. They are read
from env vars (`AKIYAJAPAN_EMAIL`, `AKIYAJAPAN_PASSWORD`), optionally via a
gitignored `.env`. See README.
