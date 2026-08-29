"""akiya — command-line entry point.

Commands:
  scrape      run sources, normalize, filter, upsert the store, show the diff
  list        query the stored listings
  diff        show what changed on the most recent scrape (re-runs upsert dry)
  leads       re-check the handoff's known leads against the store
  underwrite  run the P&L model for a price / scenario
  serve       JSON API + photo server for the iOS swipe app
"""

from __future__ import annotations

import argparse
import sys

from pathlib import Path

from . import filters
from .display import change_report, console, listings_table, underwrite_report
from .fetch import Client
from .sources import REGISTRY
from .store import Store
from .underwrite import Assumptions, run, sensitivity

# Handoff leads, keyed by the store key we expect once scraped.
HANDOFF_LEADS = {
    "blogspot:S-03-004": "Suttsu ¥4.8M 5LDK (unregistered)",
    "blogspot:S-19-017": "Yoichi ¥6.8M 3LDK (no parking)",
    "blogspot:S-11-020": "Kutchan ¥15M (under negotiation)",
    "homes:47650": "Otaru Zenibako ¥3.8M condo (reference — fails detached rule)",
}


def cmd_scrape(args: argparse.Namespace) -> int:
    client = Client(use_cache=not args.no_cache)
    store = Store()
    names = [args.source] if args.source else list(REGISTRY)
    all_listings = []
    try:
        for name in names:
            module = REGISTRY[name]
            console.print(f"[dim]scraping {name}…[/dim]")
            try:
                import inspect
                kwargs = {}
                if "log" in inspect.signature(module.fetch).parameters:
                    kwargs["log"] = lambda m: console.print(f"[yellow]  {m}[/yellow]")
                listings = module.fetch(client, **kwargs)
            except Exception as e:  # one bad source shouldn't sink the run
                console.print(f"[red]  {name} failed: {e}[/red]")
                continue
            console.print(f"[dim]  {name}: {len(listings)} listings[/dim]")
            all_listings.extend(listings)
    finally:
        client.close()

    filters.annotate_all(all_listings)
    report = store.upsert(all_listings)
    store.save()

    counts = {}
    for l in all_listings:
        counts[l.verdict] = counts.get(l.verdict, 0) + 1
    console.print(f"\n[bold]Scraped {len(all_listings)} listings[/bold]: " +
                  ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
    hot = change_report(report)
    return 10 if hot else 0


def cmd_list(args: argparse.Namespace) -> int:
    store = Store()
    listings = store.query(
        verdict=args.verdict, town=args.town, max_price=args.max_price, source=args.source
    )
    listings_table(listings, title="Stored listings")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    # Diff without re-scraping: compare store vs a fresh scrape from cache only.
    client = Client(use_cache=True)
    store = Store()
    all_listings = []
    try:
        for name in REGISTRY:
            try:
                all_listings.extend(REGISTRY[name].fetch(client))
            except Exception as e:
                console.print(f"[red]{name} failed: {e}[/red]")
    finally:
        client.close()
    filters.annotate_all(all_listings)
    # Dry compare: don't persist.
    report = store.upsert(all_listings)
    hot = change_report(report)
    return 10 if hot else 0


def cmd_leads(args: argparse.Namespace) -> int:
    store = Store()
    console.print("[bold]Handoff leads — current status[/bold]")
    found = []
    for key, desc in HANDOFF_LEADS.items():
        l = store.get(key)
        if l:
            console.print(f"  [green]✓[/green] {key}: {desc}")
            console.print(f"      → {l.verdict}: {l.status}, {l.town} ¥{(l.price_yen or 0):,}, "
                          f"built {l.build_year}, seen {l.first_seen}→{l.last_seen}")
            found.append(l)
        else:
            console.print(f"  [yellow]?[/yellow] {key}: {desc} — [dim]not in store (run scrape)[/dim]")
    if found:
        listings_table(found, title="Leads")
    return 0


def cmd_images(args: argparse.Namespace) -> int:
    from .images import download_all

    store = Store()
    listings = store.query(verdict=args.verdict, town=args.town)
    if not args.include_rejects and args.verdict is None:
        listings = [l for l in listings if l.verdict != "reject"]
    # SUUMO: upgrade thumbnails to hi-res in place; with --detail also pull the
    # full gallery from each detail page (throttled ≥30s/request, disk-cached).
    from .sources import suumo

    client = Client(use_cache=not args.no_cache) if args.detail else None
    for l in listings:
        if l.source != "suumo":
            continue
        if client is not None:
            try:
                l.image_urls = suumo.fetch_gallery(client, l)
            except Exception as e:  # keep going; the thumbnails still work
                console.print(f"[yellow]detail fetch failed for {l.key}: {e}[/yellow]")
                l.image_urls = [suumo.hires(u) for u in l.image_urls]
        else:
            l.image_urls = [suumo.hires(u) for u in l.image_urls]
    with_urls = [l for l in listings if l.image_urls]
    console.print(f"[dim]downloading images for {len(with_urls)} listings…[/dim]")
    total = download_all(with_urls, force=args.force)
    # Persist the local_images paths back to the store.
    for l in with_urls:
        stored = store.get(l.key)
        if stored:
            stored.local_images = l.local_images
            stored.image_urls = l.image_urls
    store.save()
    console.print(f"[green]saved {total} images[/green] under data/images/")
    return 0


def cmd_gallery(args: argparse.Namespace) -> int:
    from .gallery import build

    store = Store()
    listings = store.query(verdict=args.verdict, town=args.town, max_price=args.max_price)
    out = Path(args.output)
    build(listings, out)
    console.print(f"[green]gallery written:[/green] {out}  ({len(listings)} listings)")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .serve import serve

    serve(host=args.host, port=args.port)
    return 0


def cmd_underwrite(args: argparse.Namespace) -> int:
    kw = dict(
        price_yen=args.price,
        reno_mult=args.reno_mult,
        winter_nights=args.winter_nights,
        winter_adr_usd=args.adr,
        shoulder_nights=args.shoulder_nights,
        mgmt_pct=args.mgmt_pct,
        fx=args.fx,
    )
    if args.reno_yen is not None:
        kw["reno_yen"] = args.reno_yen
    if args.accom_tax:
        kw["accommodation_tax_pct"] = 0.03
    a = Assumptions(**kw)
    result = run(a)
    sens = sensitivity(a)
    label = args.label or f"¥{args.price:,} @ reno {args.reno_mult}×, {args.winter_nights}n×${args.adr:g}"
    underwrite_report(label, result, sens, args.fx)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="akiya", description=__doc__.splitlines()[1])
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("scrape", help="run sources and update the store")
    sp.add_argument("--source", choices=list(REGISTRY), help="only this source")
    sp.add_argument("--no-cache", action="store_true", help="bypass the disk cache")
    sp.set_defaults(func=cmd_scrape)

    lp = sub.add_parser("list", help="query stored listings")
    lp.add_argument("--verdict", choices=["pass", "stretch", "flagged", "reject"])
    lp.add_argument("--town")
    lp.add_argument("--max-price", type=int)
    lp.add_argument("--source", choices=list(REGISTRY))
    lp.set_defaults(func=cmd_list)

    dp = sub.add_parser("diff", help="what changed on the last scrape (from cache)")
    dp.set_defaults(func=cmd_diff)

    lep = sub.add_parser("leads", help="re-check the handoff's known leads")
    lep.set_defaults(func=cmd_leads)

    ip = sub.add_parser("images", help="download listing photos into data/images/")
    ip.add_argument("--verdict", choices=["pass", "stretch", "flagged", "reject"])
    ip.add_argument("--town")
    ip.add_argument("--include-rejects", action="store_true", help="also fetch reject photos")
    ip.add_argument("--force", action="store_true", help="re-download even if present")
    ip.add_argument("--detail", action="store_true",
                    help="SUUMO: fetch each detail page for the full hi-res gallery (slow: ≥30s each)")
    ip.add_argument("--no-cache", action="store_true", help="bypass today's disk cache for --detail")
    ip.set_defaults(func=cmd_images)

    gp = sub.add_parser("gallery", help="build a self-contained HTML gallery to eyeball")
    gp.add_argument("-o", "--output", default="data/gallery.html")
    gp.add_argument("--verdict", choices=["pass", "stretch", "flagged", "reject"])
    gp.add_argument("--town")
    gp.add_argument("--max-price", type=int)
    gp.set_defaults(func=cmd_gallery)

    up = sub.add_parser("underwrite", help="run the P&L model")
    up.add_argument("--price", type=int, required=True, help="purchase price in yen")
    up.add_argument("--reno-mult", type=float, default=3.0)
    up.add_argument("--reno-yen", type=int, help="explicit reno cost (overrides --reno-mult)")
    up.add_argument("--winter-nights", type=int, default=100)
    up.add_argument("--shoulder-nights", type=int, default=0)
    up.add_argument("--adr", type=float, default=300.0, help="winter ADR in USD")
    up.add_argument("--mgmt-pct", type=float, default=0.20)
    up.add_argument("--fx", type=float, default=150.0)
    up.add_argument("--accom-tax", action="store_true", help="apply 3% (Kutchan/Niseko)")
    up.add_argument("--label")
    up.set_defaults(func=cmd_underwrite)

    svp = sub.add_parser("serve", help="JSON API + photos for the iOS swipe app")
    svp.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 to reach from a phone")
    svp.add_argument("--port", type=int, default=8787)
    svp.set_defaults(func=cmd_serve)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
