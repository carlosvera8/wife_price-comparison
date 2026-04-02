from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

console = Console()

_CONFIDENCE_COLORS = {
    "high": "green",
    "medium": "yellow",
    "low": "red",
}


def render_results(query: str, zip_code: str, results: list[dict]) -> None:
    console.print()
    console.print(f"[bold]Product:[/bold] {query.title()}")
    console.print(f"[bold]ZIP:[/bold]     {zip_code}")
    console.print()

    valid = [r for r in results if r.get("unit_price") is not None]
    invalid = [r for r in results if r.get("unit_price") is None]

    if not valid and not invalid:
        console.print("[red]No results found. Try a different product name or ZIP code.[/red]")
        return

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan", expand=False)
    table.add_column("Retailer", min_width=12)
    table.add_column("Product", min_width=35)
    table.add_column("Price", justify="right", min_width=8)
    table.add_column("Unit Price", justify="right", min_width=16)
    table.add_column("Units", justify="right", min_width=6)
    table.add_column("Conf.", justify="center", min_width=6)

    for i, r in enumerate(valid):
        is_best = i == 0
        row_style = "bold green" if is_best else ""

        unit_label = r.get("unit_label", "unit")
        unit_price = r["unit_price"]
        unit_count = r.get("unit_count", "?")
        confidence = r.get("confidence", "low")
        conf_color = _CONFIDENCE_COLORS.get(confidence, "white")

        name = r["name"]
        if len(name) > 45:
            name = name[:43] + "…"

        table.add_row(
            r["retailer"],
            name,
            r["price_str"],
            f"${unit_price:.4f}/{unit_label}",
            str(unit_count),
            f"[{conf_color}]{confidence[0].upper()}[/{conf_color}]",
            style=row_style,
        )

    # Retailers that returned no usable data
    for r in invalid:
        table.add_row(
            r["retailer"],
            r["name"][:43] + "…" if len(r["name"]) > 45 else r["name"],
            r.get("price_str", "—"),
            "[dim]n/a[/dim]",
            "[dim]—[/dim]",
            "[dim]—[/dim]",
        )

    console.print(table)

    if valid:
        best = valid[0]
        console.print(
            f"\n[bold green]BEST VALUE:[/bold green] "
            f"[bold]{best['retailer']}[/bold] — {best['name'][:60]} "
            f"([green]${best['unit_price']:.4f}/{best.get('unit_label', 'unit')}[/green])"
        )
    console.print()
