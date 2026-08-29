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
```

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

akiyajapan.com is handled separately (login required, anti-bot) — see below.

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

### akiyajapan.com credentials (never committed)

akiyajapan.com blocks non-browser agents and needs a logged-in session. Put
credentials in the environment (or a gitignored `.env`), never in code:

```bash
export AKIYAJAPAN_EMAIL="you@example.com"
export AKIYAJAPAN_PASSWORD="…"
```

## Development

```bash
uv run pytest          # parser/normalizer/filter/store/underwrite tests (fixture-driven, offline)
```

Tests run against saved real-page fixtures in `tests/fixtures/`, so they're
fast and don't hit the network.
