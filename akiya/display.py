"""Rich terminal rendering for listings, change reports, and underwriting."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from .models import Listing
from .underwrite import Result

# Force a comfortable width so wide tables don't wrap into unreadable columns
# on a narrow terminal; rich still fits to the real terminal when wider.
console = Console(width=140)

VERDICT_STYLE = {
    "pass": "bold green",
    "stretch": "yellow",
    "flagged": "cyan",
    "reject": "dim red",
}


def _yen(v: int | None) -> str:
    return f"¥{v:,}" if v is not None else "—"


def _usd(v: int | None, fx: float = 150.0) -> str:
    return f"${round(v / fx):,}" if v is not None else "—"


def listings_table(listings: list[Listing], title: str = "Listings", show_usd: bool = True) -> None:
    if not listings:
        console.print(f"[dim]{title}: none[/dim]")
        return
    t = Table(title=f"{title} ({len(listings)})", show_lines=False, expand=False)
    t.add_column("verdict", no_wrap=True)
    t.add_column("town", no_wrap=True)
    t.add_column("price", justify="right", no_wrap=True)
    if show_usd:
        t.add_column("~USD", justify="right", no_wrap=True)
    t.add_column("layout", no_wrap=True)
    t.add_column("bldg m²", justify="right", no_wrap=True)
    t.add_column("built", justify="right", no_wrap=True)
    t.add_column("id", no_wrap=True)
    t.add_column("notes", no_wrap=True, overflow="ellipsis", max_width=48)
    for l in listings:
        style = VERDICT_STYLE.get(l.verdict or "", "")
        notes = "; ".join(l.verdict_reasons or []) or "—"
        row = [
            f"[{style}]{l.verdict or '?'}[/{style}]",
            l.town or "—",
            _yen(l.price_yen),
        ]
        if show_usd:
            row.append(_usd(l.price_yen))
        row += [
            l.layout or "—",
            f"{l.building_m2:.0f}" if l.building_m2 else "—",
            str(l.build_year or "—"),
            f"{l.source}:{l.source_id}",
            notes,
        ]
        t.add_row(*row)
    console.print(t)


def change_report(report: dict[str, list[Listing]]) -> bool:
    """Render the diff. Returns True if there are new *passing/stretch* listings."""
    labels = {
        "new": ("NEW LISTINGS", "bold green"),
        "price": ("PRICE CHANGED", "yellow"),
        "status": ("STATUS CHANGED", "cyan"),
        "gone": ("GONE (not seen this run)", "dim"),
    }
    any_news = False
    hot = False
    for key, (label, style) in labels.items():
        rows = report.get(key, [])
        if not rows:
            continue
        any_news = True
        # Actionable rows go in the table; rejects are just counted so the
        # signal (a new buyable house) isn't buried under sold/condo noise.
        actionable = [l for l in rows if l.verdict != "reject"]
        rejects = len(rows) - len(actionable)
        console.print(f"\n[{style}]━━ {label} ({len(rows)}) ━━[/{style}]")
        if actionable:
            actionable.sort(key=lambda l: {"pass": 0, "stretch": 1, "flagged": 2}.get(l.verdict or "z", 9))
            listings_table(actionable, title=label, show_usd=True)
        if rejects:
            console.print(f"  [dim]+ {rejects} rejected (sold / condo / land / pre-1981 / too dear)[/dim]")
        if key == "new":
            hot = any(l.verdict in ("pass", "stretch") for l in actionable)
    if not any_news:
        console.print("[dim]No changes since last run.[/dim]")
    return hot


def underwrite_report(listing_label: str, result: Result, sens: list[dict], fx: float) -> None:
    bar = "[bold green]PASS[/bold green]" if result.passes_bar else "[bold red]FAIL[/bold red]"
    console.print(f"\n[bold]Underwriting: {listing_label}[/bold]  →  6% net bar: {bar}")

    acq = Table(title="Acquisition (all-in)", show_header=False)
    acq.add_column("item")
    acq.add_column("USD", justify="right")
    for k, v in result.acquisition_breakdown.items():
        acq.add_row(k, f"${v:,}")
    acq.add_row("[bold]ALL-IN[/bold]", f"[bold]${result.all_in_usd:,}[/bold]")
    console.print(acq)

    pl = Table(title="Annual P&L", show_header=False)
    pl.add_column("item")
    pl.add_column("USD", justify="right")
    pl.add_row("gross revenue", f"${result.gross_revenue_usd:,}")
    for k, v in result.opex_breakdown.items():
        pl.add_row(f"  − {k}", f"(${v:,})")
    pl.add_row("[bold]NOI (pre-JP-tax)[/bold]", f"[bold]${result.noi_usd:,}[/bold]")
    pl.add_row("net yield", f"{result.net_yield:.1%}")
    pl.add_row("after JP withholding", f"${result.after_tax_noi_usd:,} ({result.after_tax_yield:.1%})")
    if result.accommodation_tax_collected_usd:
        pl.add_row("[dim]accom. tax (guest-paid)[/dim]", f"[dim]${result.accommodation_tax_collected_usd:,}[/dim]")
    console.print(pl)

    s = Table(title="Sensitivity — net yield")
    s.add_column("reno ×", justify="right")
    s.add_column("winter nights", justify="right")
    s.add_column("all-in", justify="right")
    s.add_column("NOI", justify="right")
    s.add_column("net yield", justify="right")
    for row in sens:
        yld = row["net_yield"]
        style = "green" if row["passes"] else "red"
        s.add_row(
            f"{row['reno_mult']:g}",
            str(row["winter_nights"]),
            f"${row['all_in_usd']:,}",
            f"${row['noi_usd']:,}",
            f"[{style}]{yld:.1%}[/{style}]",
        )
    console.print(s)
