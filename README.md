# akiya — Hokkaido fixer-upper hunter

Tooling to **find, monitor, and underwrite** cheap detached houses in Hokkaido
for a legal minpaku (short-term-rental) Airbnb, operated remotely. It scrapes
the akiya/resale sources that actually carry Shiribeshi-region inventory,
normalizes the messy Japanese listing text into a clean schema, applies the
hard buy-criteria, tracks what's new/changed/gone between runs, and runs the
P&L model against a 6% net-yield bar.

See `HANDOFF.md` for the full strategy, legal constraints, and target-market
research. See `DECISIONS.md` for why the scrapers work the way they do.

## Setup

```bash
uv sync                        # install deps
uv run playwright install chromium   # for sites behind JS challenges / logins
```

## Commands

```bash
uv run akiya scrape            # scrape all sources, filter, update the store, show the diff
uv run akiya scrape --source blogspot   # just one source (blogspot|homes|suumo)
uv run akiya scrape --no-cache          # bypass today's disk cache

uv run akiya list                       # all stored listings, cheapest first
uv run akiya list --verdict pass        # only clean buys (pass|stretch|flagged|reject)
uv run akiya list --town Otaru --max-price 7500000

uv run akiya diff              # what changed on the last scrape (from cache)
uv run akiya leads            # re-check the handoff's known leads

uv run akiya underwrite --price 6800000 --reno-mult 3 --winter-nights 90 --adr 260
uv run akiya underwrite --price 3000000 --accom-tax --label "Kutchan candidate"

uv run akiya images                     # download photos (skips rejects by default)
uv run akiya images --detail            # SUUMO: also fetch each detail page for the full hi-res gallery (≥30s each)
uv run akiya gallery                    # build data/gallery.html to eyeball everything
uv run akiya gallery --verdict pass -o data/pass.html
```

### Eyeballing + taste labeling

`akiya gallery` builds a **self-contained HTML page** of listing cards — photos,
price (¥ and ~$), layout/areas/build year, verdict badge, and a link to the
source — ordered buyable-first and filterable by verdict. Each card has 👍 / 👎 /
🚫 buttons; your labels save to the browser's localStorage, and **⬇ export taste
labels** downloads them as `taste_labels.json` — a labeled dataset for a future
"which places look good/bad" model. Run `akiya images` first so the gallery
shows local photos. Open the file in any browser (it references photos under
`data/images/`, so keep it in `data/`).

`scrape` exits 10 (not 0) when there are **new passing/stretch listings**, so
you can wire it to a notifier or cron:

```bash
uv run akiya scrape && echo "nothing new" || echo "NEW LISTINGS — go look"
```

## Sources

| Source | What it covers | Method |
|---|---|---|
| `blogspot` | akiyabank.blogspot.com — Shiribeshi/Niseko akiya bank | JSON feed, one request |
| `homes` | LIFULL HOME'S akiya bank, target towns | HTML + browser (solves the AWS WAF JS challenge) |
| `suumo` | General used-detached-house market (Otaru, Furano) | HTML, throttled ≥30s, no `sort=` URLs |
| `akiyajapan` | English aggregator — richest source, full inventory | Documented public JSON API (`/api/v1/properties/search`); exact JPY, labeled sizes, features; honest UA, ≤60 req/min, attributed |

## The filter (hard criteria)

Detached only · built ≥ 1981 · ≤ ¥7.5M (≤ ¥10M = "stretch") · town ordinance
vetted · registered/clear title · reject structural reno. Every listing gets a
verdict — `pass` / `stretch` / `flagged` / `reject` — with reasons; nothing is
silently dropped.

**Before any offer, verify the town's minpaku ordinance in `data/ordinances.md`.**

## Browser-gated sites

HOME'S sits behind an AWS WAF JS challenge; the scraper auto-falls back to a
headless Chromium (via Playwright) that solves it. If a challenge won't clear
headless, run headed:

```bash
AKIYA_HEADED=1 uv run akiya scrape --source homes
```

### akiyajapan.com

Uses their **documented public JSON API** (`/api/v1/properties/search`) — exact
JPY prices, separately labeled house/land sizes, bedrooms, build year, features,
photos, and full pagination (no per-city cap). No login/credentials. We send an
honest tool User-Agent, stay under their 60 req/min limit, cache, and record
their attribution string. **Note (owner-approved tradeoff):** robots.txt lists
`Disallow: /api` even though llms.txt advertises this API for assistants; see
`DECISIONS.md` for the full rationale and residual risk.

## Development

```bash
uv run pytest          # parser/normalizer/filter/store/underwrite tests (fixture-driven, offline)
```

Tests run against saved real-page fixtures in `tests/fixtures/`, so they're
fast and don't hit the network.

## Pi deployment (alerts + Telegram chat)

Runs on the always-on Raspberry Pi (`ssh pi`), repo at `~/Code/japan-house-finder`:

- **Daily alerts (cron)**: `bin/scrape_and_notify.py` scrapes, diffs the store,
  and DMs Telegram only when genuinely new pass/stretch listings appear —
  headless `claude -p` writes the analyst summary (deterministic fallback).
  Crontab: `0 8 * * *` (quiet) and `0 15 * * *` with `AKIYA_DIGEST=1`
  (heartbeat even when nothing is new).
- **Chat with Claude from Telegram**: `bin/telegram_claude_bridge.py` long-polls
  the bot, pipes owner messages to `claude -p --continue` (tools limited to
  Read/Grep/Glob + the akiya CLI), replies in the DM. `/new` resets the
  conversation. Runs via `deploy/akiya-bridge.service` (systemd user unit,
  linger enabled).
- **Secrets**: bot token + chat id live in gitignored `.env.telegram` next to
  the repo root (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`).

## iOS app — "Tinder for akiya" (`ios/AkiyaSwipe`)

SwiftUI app (iOS 17+) that turns the store into a swipe deck. Built on
[Shuffle](https://github.com/mac-gallagher/Shuffle) (SPM, ~1k★) for the card
stack; everything inside the card is SwiftUI.

- **Card** = tap-through photo pager (photos shrink-to-fit on a blurred fill,
  never cropped), price ¥/~$, verdict badge, town/address, layout·m²·year, flags.
  Tap the left 30% to go back a photo, anywhere else to advance.
- **Swipe right / ❤️ = like, left / ✕ = pass, ↶ = undo, ⓘ = profile.**
- **Profile sheet** shows every scraped field: photos, facts, verdict reasons,
  flags, the per-source `raw` specs (agent remarks, station, features…), and the
  **contact** — the source listing page (Open / Share). The scrapers don't
  extract a phone/agent field separately; the source page is where the contact
  form / agent lives.
- **Likes** and **Passed** lists are stored **only on the device**
  (`Documents/swipes.json`, full listing snapshots). Passed listings are never
  re-shown; swipe a row to forget/like/pass again.
- **Data**: `Resources/listings.json` is a bundled snapshot so the app works
  offline. Set a server URL in Settings to pull live data from `akiya serve`.
- Deck hides `reject` verdicts by default (toggle in Settings) and orders
  pass → stretch → flagged, cheapest first.

```bash
uv run akiya serve --host 0.0.0.0 --port 8787     # JSON API + downloaded photos
# then in the app: Settings → Server → http://<your-mac-ip>:8787
open ios/AkiyaSwipe/AkiyaSwipe.xcodeproj           # build & run (Xcode 26)
```

Refresh the bundled snapshot after a scrape:

```bash
uv run python -c "
from akiya.serve import build_payload; from akiya.store import Store; import json
p=build_payload(Store())
for l in p['listings']: l['photos']=l['image_urls']; l['local_images']=[]
json.dump(p, open('ios/AkiyaSwipe/AkiyaSwipe/Resources/listings.json','w'), ensure_ascii=False)"
```

### Photo resolution

SUUMO's list page only exposes 192×144 thumbnails, but its CDN is a resizer
(`resizeImage?src=…&w=N`) that serves the same photo up to ~1200px wide, so the
scraper rewrites every SUUMO URL to `w=1200` (width-only keeps floor plans
un-distorted). `akiya images --detail` additionally fetches each non-reject
SUUMO detail page — throttled ≥30s and disk-cached like every SUUMO request —
to pick up the full gallery (typically 5–24 photos vs 3 on the list page).
akiyajapan serves 640×480 originals and Blogspot `s1600` originals already.
