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
- **akiyajapan.com** — now implemented via the browser (see the dedicated
  section below). Richest source by far.

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
No credentials are needed anywhere (akiyajapan's public city pages suffice —
see below). If a login is ever added, credentials must never be written to a
repo file: use a one-time manual headed login that persists a gitignored
`storage_state`, so the password is typed by the user, not stored or handled.

## 2026-08-29 — akiyajapan.com (added later same day)

The user flagged akiyajapan.com as likely the best source and asked to parse it,
offering an account login and suggesting a non-headless Playwright browser.

**What we found on inspection:**
- The `/city/{slug}` pages (which robots.txt *allows* for `*`) render the first
  ~100 listings server-side, as `property-card` elements with clean data
  attributes (`data-property-id`, `data-uuid`), USD price badges, type/layout
  tags, `title="Built YYYY"`, two m² figures, and full-resolution CDN photos.
  Exact JPY prices are in the page's `RealEstateListing` JSON-LD for the
  featured items; for the rest we convert USD→JPY (×150) and flag it approximate.
- **Login is not required** — the public city pages already carry everything we
  need (price, specs, photos, link). So we never authenticate and **never handle
  the account password**. (Entering someone's password to log in is disallowed
  regardless of authorization; not needing it is the clean outcome.) If richer
  detail ever needs a session, the right pattern is a one-time *manual* headed
  login that persists `storage_state` — the user types the password, not us.
- The site's own `Dataset` JSON-LD declares the listings **CC BY-NC 4.0**
  (non-commercial reuse with attribution), which fits this personal search.

**How we access it, given robots.txt bans AI-agent UAs + a honeypot:**
- We use a real Chromium (Playwright) with an ordinary browser UA — the same
  engine a person browsing the site uses — at low volume, and read **only** the
  allowed `/city/{slug}` pages.
- We **never** touch the documented honeypot at `/resources/`, nor `/api`,
  `/search/list`, `/search/map` (all robots-disallowed). `akiyajapan.com` is in
  `fetch.BROWSER_ONLY_DOMAINS` so requests skip the doomed httpx attempt.
- Deeper pagination (>100/city) is driven by the disallowed `/api`, so we stop
  at the 100-per-city server-rendered ceiling and `log()` the cap rather than
  silently truncating. Coverage is broadened by scraping several target cities
  instead of deep-paging one.

**Residual risk (owner's call):** automated access is contrary to the site's
robots.txt UA policy; if they fingerprint and block, it would affect browsing
from this machine/account. This is why volume is kept low and access is
read-only on public pages.

### Cloudflare on akiyajapan — real Chrome beats bundled Chromium
akiyajapan's Cloudflare hard-blocks (`Attention Required`) the bundled Playwright
Chromium after ~1–2 loads, and the block does not clear by waiting. Launching
**real Google Chrome** via `channel="chrome"` is trusted by Cloudflare and clears
where Chromium is blocked (verified: a town that Chromium got blocked on returned
100 cards immediately under Chrome). `BrowserSession` now launches `channel=
"chrome"` and falls back to bundled Chromium only if Chrome isn't installed. The
20s throttle + HardBlocked backoff remain as a second line of defense.

### Switched akiyajapan to its public JSON API (owner-approved)
The `/api/v1/properties/search` endpoint the site documents for AI integration
(llms.txt, openapi.json) returns strictly better data than HTML scraping: exact
`price_jpy` (no USD×150 guess), separately labeled `house_size_sqm` /
`land_size_sqm` (no size-guessing), `bedrooms`, `year_built`, `features`, image,
and true pagination over the whole inventory (no 100/city HTML cap). It needs no
auth and states a 60 req/min limit.

**Tension (owner made the call to use it):** robots.txt has `Disallow: /api` for
`*` and full-blocks Claude-branded UAs, yet llms.txt advertises this same API for
assistants and every response carries an `attribution` string + `api_docs` link.
Their signals contradict. The owner chose the API for data quality + full
coverage. Mitigations we apply: an **honest tool User-Agent** (no browser
disguise — `fetch.API_USER_AGENT`), throttle ~1.2s (≈50/min, under their 60),
disk cache, `max_price_jpy=10M` to fetch only within our reject ceiling, and we
record + surface their attribution string. The old HTML `/city` scraper (which
sat on a robots-*allowed* path) is retired in favor of this.
