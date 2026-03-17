import json
import os
from collections import defaultdict
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

import config

console = Console()


def load_raw_data(filepath=None):
    if filepath is None:
        filepath = os.path.join(config.RAW_DATA_DIR, "gsc_raw_data.json")

    if not os.path.exists(filepath):
        console.print(Panel(
            f"Raw data not found at [cyan]{filepath}[/cyan]\n\n"
            "Run [bold green]python main.py extract[/bold green] first.",
            title="[bold red]Missing Data[/bold red]",
            border_style="red",
        ))
        return None

    with open(filepath) as f:
        return json.load(f)


def _compute_trend(monthly_clicks):
    """Classify trend based on first-half vs second-half click comparison."""
    if len(monthly_clicks) < 2:
        return "stable"
    mid = len(monthly_clicks) // 2
    first_half = sum(monthly_clicks[:mid]) / max(mid, 1)
    second_half = sum(monthly_clicks[mid:]) / max(len(monthly_clicks) - mid, 1)
    if first_half == 0 and second_half == 0:
        return "stable"
    if first_half == 0:
        return "new"
    ratio = second_half / first_half
    if ratio > 1.3:
        return "rising"
    if ratio < 0.7:
        return "declining"
    return "stable"


def process_query_page_pairs(raw_data):
    """Aggregate raw GSC rows into query-page pair documents."""
    rows = raw_data.get("rows", [])
    if not rows:
        console.print("  [yellow]No rows to process.[/yellow]")
        return [], []

    query_page_agg = defaultdict(lambda: {
        "clicks": 0, "impressions": 0,
        "position_sum": 0, "ctr_sum": 0, "count": 0,
        "countries": set(), "devices": set(),
        "monthly_clicks": defaultdict(int),
        "dates": set(),
    })

    page_agg = defaultdict(lambda: {
        "clicks": 0, "impressions": 0,
        "position_sum": 0, "ctr_sum": 0, "count": 0,
        "queries": set(), "monthly_clicks": defaultdict(int),
    })

    for row in rows:
        keys = row.get("keys", [])
        if len(keys) < 5:
            continue

        query, page, date_str, country, device = keys[:5]
        clicks = row.get("clicks", 0)
        impressions = row.get("impressions", 0)
        ctr = row.get("ctr", 0)
        position = row.get("position", 0)
        month_key = date_str[:7]

        qp_key = (query, page)
        entry = query_page_agg[qp_key]
        entry["clicks"] += clicks
        entry["impressions"] += impressions
        entry["position_sum"] += position * impressions
        entry["ctr_sum"] += ctr * impressions
        entry["count"] += 1
        entry["countries"].add(country)
        entry["devices"].add(device)
        entry["monthly_clicks"][month_key] += clicks
        entry["dates"].add(date_str)

        p_entry = page_agg[page]
        p_entry["clicks"] += clicks
        p_entry["impressions"] += impressions
        p_entry["position_sum"] += position * impressions
        p_entry["ctr_sum"] += ctr * impressions
        p_entry["count"] += 1
        p_entry["queries"].add(query)
        p_entry["monthly_clicks"][month_key] += clicks

    query_docs = []
    for (query, page), data in query_page_agg.items():
        imp = max(data["impressions"], 1)
        avg_pos = round(data["position_sum"] / imp, 1)
        avg_ctr = round((data["ctr_sum"] / imp) * 100, 2)
        sorted_months = sorted(data["monthly_clicks"].keys())
        monthly_clicks_list = [data["monthly_clicks"][m] for m in sorted_months]
        trend = _compute_trend(monthly_clicks_list)

        text = (
            f"Query: '{query}' | Page: {page} | "
            f"Clicks: {data['clicks']:,} | Impressions: {data['impressions']:,} | "
            f"CTR: {avg_ctr}% | Avg Position: {avg_pos} | Trend: {trend}"
        )

        doc_id = f"qp_{hash((query, page)) & 0xFFFFFFFF:08x}"
        metadata = {
            "query": query,
            "page": page,
            "clicks": data["clicks"],
            "impressions": data["impressions"],
            "ctr": avg_ctr,
            "position": avg_pos,
            "trend": trend,
            "countries": ",".join(sorted(data["countries"])),
            "devices": ",".join(sorted(data["devices"])),
            "first_date": min(data["dates"]),
            "last_date": max(data["dates"]),
            "data_points": data["count"],
        }
        query_docs.append({"id": doc_id, "text": text, "metadata": metadata})

    page_docs = []
    for page, data in page_agg.items():
        imp = max(data["impressions"], 1)
        avg_pos = round(data["position_sum"] / imp, 1)
        avg_ctr = round((data["ctr_sum"] / imp) * 100, 2)
        sorted_months = sorted(data["monthly_clicks"].keys())
        monthly_clicks_list = [data["monthly_clicks"][m] for m in sorted_months]
        trend = _compute_trend(monthly_clicks_list)
        query_count = len(data["queries"])
        top_queries = sorted(data["queries"])[:10]

        text = (
            f"Page: {page} | Clicks: {data['clicks']:,} | "
            f"Impressions: {data['impressions']:,} | CTR: {avg_ctr}% | "
            f"Avg Position: {avg_pos} | Queries: {query_count} | "
            f"Trend: {trend} | Top queries: {', '.join(top_queries)}"
        )

        doc_id = f"pg_{hash(page) & 0xFFFFFFFF:08x}"
        metadata = {
            "page": page,
            "clicks": data["clicks"],
            "impressions": data["impressions"],
            "ctr": avg_ctr,
            "position": avg_pos,
            "trend": trend,
            "query_count": query_count,
            "data_points": data["count"],
        }
        page_docs.append({"id": doc_id, "text": text, "metadata": metadata})

    trends = defaultdict(int)
    for doc in query_docs:
        trends[doc["metadata"]["trend"]] += 1

    summary = Table(
        box=box.ROUNDED,
        border_style="green",
        title="[bold]Processing Summary[/bold]",
        title_style="bold white",
        padding=(0, 2),
    )
    summary.add_column("Metric", style="white")
    summary.add_column("Count", style="cyan", justify="right")
    summary.add_row("Raw rows", f"{len(rows):,}")
    summary.add_row("Query-page pairs", f"{len(query_docs):,}")
    summary.add_row("Unique pages", f"{len(page_docs):,}")
    summary.add_row("", "")
    for t in ["rising", "stable", "declining", "new"]:
        style = {"rising": "green", "stable": "white", "declining": "red", "new": "blue"}.get(t, "white")
        summary.add_row(f"  [{style}]{t.capitalize()}[/{style}] queries", f"[{style}]{trends.get(t, 0):,}[/{style}]")

    console.print(summary)
    console.print()

    return query_docs, page_docs


def process_data(raw_data_path=None):
    raw_data = load_raw_data(raw_data_path)
    if raw_data is None:
        return None, None
    return process_query_page_pairs(raw_data)
