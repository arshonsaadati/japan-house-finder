# Japan Fixer-Upper → Airbnb Project

Context file for Claude Code sessions. Last updated: 2026-08-29.
Owner: Arshon — US citizen, non-resident of Japan, based in Los Angeles. Cash purchase (no JP financing).
FX convention throughout: ¥150/USD.

## Mission

Buy a cheap detached house in Japan (Hokkaido focus, Shiribeshi region leading), renovate it, and operate it as a **legal** short-term rental (minpaku), managed remotely from LA. Original envelope: **$200K all-in**. Current working plan (merged from a parallel research session): **~$50K purchase (≤ ¥7.5M) + renovation on top**.

Immediate goal of code sessions: build tooling to find, monitor, and underwrite candidate listings — inventory on akiya sites is thin and churns fast, so automation beats manual browsing.

## Legal & regulatory constraints (verified Aug 2026 — re-verify before acting, this moves fast)

- No restriction on foreign/non-resident freehold ownership. Buying grants no visa.
- **FEFTA Form 22** must be filed with MoF via Bank of Japan within **20 days** of acquisition (mandatory for non-residents since 2026-04-01). Real penalties for skipping.
- Nationality now disclosed at ownership registration (2026 change).
- **Minpaku (住宅宿泊事業法)**: notification to municipality → 届出番号 displayed on listing. **180-night/year cap** (counted by check-in; year runs Apr 1–Apr 1). Cap barely binds for a ski property (~100–120 nights of winter demand).
- **Non-resident owner MUST contract a registered management company (住宅宿泊管理業者).** This is law, not preference. Management-company availability is a site-selection criterion.
- Municipalities can restrict further — since 2026-07-15 national guidance allows zero-day zones (local bans). **Check the town's minpaku ordinance before shortlisting any property.**
- Condo/HOA bylaws overwhelmingly ban minpaku → **detached houses only**.
- 365-day alternative: Hotel Business Act simple-lodging license (簡易宿所) — stricter fire/zoning/building bar. Tokku minpaku is effectively closed to new entrants (Osaka suspended new applications 2026-05-29).
- Enforcement: national system cross-matches platform listings vs. registry (live Apr 2026).
- **Taxes**: 20.42% withholding on rent paid to non-residents, reconciled via annual return; requires a tax agent (納税管理人). Annual fixed-asset + city-planning tax. Hokkaido prefecture-wide accommodation tax since Apr 2026; Kutchan and Niseko Town charge a flat 3% (prefectural portion inside it) — operator collects/remits.

## Financial model (underwriting rules)

Budget template at $200K all-in: purchase $65–95K · closing ~7% · reno $55–80K · furnishing ~$13K · contingency $13–20K. At the $50K-purchase plan, reno still dominates: expect **2–5× purchase price** (parallel session said 2–3×; deeper research said 3–5× for true akiya — assume the pessimistic end for snow country).

P&L shape (3BR sleeping 6–8, good ski market):
- Gross: ~100 winter nights × $265–335 + 30–40 shoulder nights × $100–135 ≈ **$30–37K/yr** (15–18% gross yield on $200K). Hokkaido non-Furano: assume near-zero shoulder nights.
- Net lands **40–60% below gross** (mgmt 15–25% of revenue, OTA 10–15%, cleaning, kerosene heating, snow clearing, insurance, taxes, tax agent) → **$13–20K/yr, 7–10% net**; after JP tax ≈ **5–8% cash-on-cash** (depreciation shelters early years).
- **Underwrite at 6% net ($12K/yr on $200K). Anything above = upside.**
- Kill scenarios: renovation overrun, bad management company, consecutive weak snow seasons. FX is ~half the USD return in both directions (ref: 2021 buyer at ¥110 whose land tripled in ¥ netted ~120% in USD at ¥150).
- Structural filter: **post-1981 (new seismic code) only.** Pre-1981 = ¥1–5M reinforcement. Avoid gut jobs (structure/roof/insulation = ¥10–20M+, often > resale value). Snow-country line items: snow-load roof, insulation (most pre-1990s rural = none), pipe freeze protection, kerosene heat 300–600 L/mo in winter.

## Target markets (ranked, merged view of both research threads)

| Rank | Area | Case | Watch-outs |
|---|---|---|---|
| 1 | **Otaru** (incl. Zenibako) | Convergent pick of both threads. Year-round canal-town tourism, proven STR demand, 40 min to Sapporo, gateway to Kiroro/Teine skiing, ~400 houses listed, cheap kominka stock | Not a true ski asset; check Otaru's minpaku ordinance & ward zones |
| 2 | **Furano** | Only Hokkaido market with real dual-season demand (lavender/Biei summer). Asahikawa airport ~1 hr. Town houses ¥5–12M exist | Resort-area land +34%/4yr — discount shrinking |
| 3 | **Yoichi / Suttsu / coastal Shiribeshi** | Cheapest live inventory found so far; Yoichi has Nikka distillery tourism, 20 min to Otaru | Thin STR comps — underwrite conservatively |
| 4 | **Rankoshi** | Niseko-discount arbitrage: same powder belt, ~25 min to Annupuri, ~35 akiya listed, $15–40K entries | Guests must accept "near Niseko"; winter driving |
| 5 | **Akaigawa (Kiroro)** | Best snow of all candidates; Club Med/Yu Kiroro anchor | ~100 bookable nights/yr, few mgmt companies, no village amenities |
| — | Kutchan proper | Watch-list only: land ¥120K+/m² (+12.3% YoY) breaks the budget; Shinkansen-2030 largely priced in. Parallel session rated it higher — keep monitoring for outliers | |
| — | Skip | Niseko/Hirafu (¥189K/m², +21.9% YoY), Rusutsu (no freehold inventory), Higashikawa (lifestyle buy) | |

Honshu benchmark (if Hokkaido fails): **Hakuba** Echoland/Misorano — best overall business case ($200K works, ~3 hr from Tokyo, dual-season, deep mgmt-company market). Secondary: Myoko (PCG/Six Senses catalyst; Six Senses targeted Dec 2028 opening, ground not broken as of Mar 2026; few mgmt companies).

## Live leads (UNVERIFIED — sourced from a parallel Claude session, re-scrape before trusting)

- Suttsu 寿都町 — ¥4.8M, 5LDK, 140.9 m², built ~1987, 679 m² lot. Flag: unregistered structure. `akiyabank.blogspot.com/2026/07/s-03-004.html`
- Yoichi 余市町 — ¥6.8M, 3LDK, 112.6 m², built 1994, 125.8 m² lot. Flag: no parking. `akiyabank.blogspot.com/2025/09/s-19-017.html`
- Otaru Zenibako — ¥3.8M condo. **Fails detached-only rule** — reference point only. `homes.co.jp/akiyabank/b-47650/`
- Kutchan — ¥15M, reportedly under negotiation. Monitor source for new entries.

## Data sources

Primary (scrape/monitor):
- `akiyabank.blogspot.com` — Shiribeshi regional akiya bank (Otaru/Kutchan/Niseko/Yoichi/Suttsu). Best single source for the target region; low volume, fast churn.
- `homes.co.jp/akiyabank/hokkaido/{city}/` — per-city akiya-bank pages (otaru, yoichi, sapporo…)
- SUUMO `suumo.jp` — general resale market (far more volume than akiya banks). JP search strings: `小樽 空き家`, `倶知安 中古住宅`, `余市 中古住宅`, `富良野 中古住宅`
- `akiyajapan.com` — English; `/city/otaru`, `/city/kutchan`, `/city/rankoshi` URL pattern; price filter ≈ ¥7,500,000
- Secondary: `allakiyas.com`, `oldhousesjapan.com`, `koryoya.com` (kominka specialist), `japanpropertycentral.com`
- Comps/revenue: AirDNA for exact-neighborhood ADR & occupancy (not town-level)

Scraping etiquette: respect robots.txt/ToS, throttle, cache pages; sites are Japanese (handle encoding, browser-translate parity not guaranteed).

## Listing filter (hard criteria)

1. Detached house (no condos/HOA)
2. Built ≥ 1981
3. Price ≤ ¥7.5M (flag ≤ ¥10M as stretch)
4. Town/zone permits minpaku for absent hosts (check ordinance)
5. Registered structure, clear title, town water/sewer preferred
6. Year-round road access; note parking (ski guests drive)
7. Reject if reno scope reads structural (roof/foundation/full insulation)

## Suggested session tasks

1. Scraper + normalizer for akiyabank.blogspot.com and Homes akiya-bank city pages → JSON/CSV (price, layout, m², build year, lot, town, flags, URL, first-seen/last-seen)
2. Diff-based new-listing alerting (inventory churns fast)
3. SUUMO query module for the JP search strings above
4. Underwriting calculator implementing the P&L model (inputs: price, reno est, nights, ADR, mgmt %, tax; output: net yield vs. 6% bar)
5. Per-town ordinance checklist table (minpaku day limits, zones, mgmt companies available) before any offer

## Open questions

- Otaru's exact minpaku ordinance terms for host-absent operators
- Realistic AirDNA comps: Otaru canal area vs. Yoichi vs. Furano town
- Buy-vs-build alternative: already-licensed operating properties at ¥25–35M (~$220–235K) — often better risk-adjusted than a remote reno; keep one eye on that market
- Confirm with JP tax accountant: depreciation schedule, 20.42% withholding mechanics, tax-agent setup

## Renovation contractor availability/quotes in Shiribeshi (labor is the binding constraint, not materials)

## Scraper recon (added 2026-08-29, this session)

- `akiyabank.blogspot.com`: use the JSON feed `/feeds/posts/default?alt=json&max-results=500` — full corpus (127 posts) in one request, full bodies in `content.$t`. Labels encode status (売却/賃貸/成約済/商談中/!只今募集中!) and municipality. robots.txt disallows `/search` (label pages, pagination) but not feeds. ~123/127 posts are sold — thin live inventory, good history.
- `homes.co.jp/akiyabank`: robots-permitted, server-rendered. Prefecture index `/akiyabank/tohoku/hokkaido/` lists all 88 municipality slugs + counts (slugs are gun+town, e.g. `yoichi_yoichi`). Detail pages `/akiyabank/b-{id}/` carry the full spec table. 544 Hokkaido listings.
- `suumo.jp`: server-rendered, richest fields on the results page. `/chukoikkodate/hokkaido_/sc_{city}/?page=N` (note trailing underscore; Sapporo = `sa_sapporo`). Never use `sort=` URLs (robots-disallowed); throttle ≥30s.
- `akiyajapan.com`: SKIP — robots.txt bans Claude/Anthropic UAs, 403s at the edge, documented scraper honeypot at `/resources/`. Redundant aggregator.
