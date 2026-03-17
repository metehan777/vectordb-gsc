from parallel import Parallel
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

import config

console = Console()

_client = None


def _get_client():
    global _client
    if _client is None:
        if not config.PARALLEL_API_KEY:
            console.print("  [yellow]PARALLEL_API_KEY not set in .env — skipping web research.[/yellow]")
            return None
        _client = Parallel(api_key=config.PARALLEL_API_KEY)
    return _client


def search_competitors(query, site_domain=None, max_results=10):
    """Search the web for competing content on a query, excluding our own site."""
    client = _get_client()
    if client is None:
        return []

    exclude = []
    if site_domain:
        exclude = [site_domain.replace("https://", "").replace("http://", "").rstrip("/")]

    source_policy = {}
    if exclude:
        source_policy["domains_exclude"] = exclude

    try:
        response = client.beta.search(
            objective=f"Find the best, most comprehensive pages ranking for: {query}",
            search_queries=[query],
            mode="fast",
            max_results=max_results,
            excerpts={"max_chars_per_result": 8000},
            **({"source_policy": source_policy} if source_policy else {}),
        )
        return [
            {
                "url": r.url,
                "title": r.title,
                "excerpts": r.excerpts or [],
            }
            for r in response.results
        ]
    except Exception as e:
        console.print(f"  [yellow]Parallel search error: {e}[/yellow]")
        return []


def extract_page(url, objective=None):
    """Scrape and extract content from a specific URL."""
    client = _get_client()
    if client is None:
        return None

    try:
        response = client.beta.extract(
            urls=[url],
            objective=objective or "Extract the full page content, headings, topics covered, and key information.",
            excerpts=True,
            full_content=True,
        )
        if response.results:
            r = response.results[0]
            return {
                "url": r.url,
                "title": r.title,
                "excerpts": r.excerpts or [],
                "full_content": r.full_content or "",
            }
    except Exception as e:
        console.print(f"  [yellow]Parallel extract error for {url}: {e}[/yellow]")
    return None


def research_query(query, own_page_url=None, site_domain=None, max_competitors=5):
    """Full research pipeline: scrape own page + search competitors for a query."""
    results = {"query": query, "own_page": None, "competitors": []}

    if own_page_url:
        results["own_page"] = extract_page(
            own_page_url,
            objective=f"Extract all content related to: {query}",
        )

    results["competitors"] = search_competitors(
        query, site_domain=site_domain, max_results=max_competitors
    )

    return results


def build_comparison_context(research_data):
    """Format research data into a context string for LLM analysis."""
    parts = []
    q = research_data["query"]
    parts.append(f"## Web Research for: \"{q}\"\n")

    own = research_data.get("own_page")
    if own:
        parts.append(f"### Your Page: {own['title']}")
        parts.append(f"URL: {own['url']}")
        content = own.get("full_content", "")
        if content:
            max_chars = 15000
            if len(content) > max_chars:
                content = content[:max_chars] + "\n[... truncated ...]"
            parts.append(f"Content:\n{content}\n")
        elif own.get("excerpts"):
            parts.append("Excerpts:")
            for ex in own["excerpts"][:5]:
                parts.append(f"  {ex[:2000]}")
            parts.append("")

    competitors = research_data.get("competitors", [])
    if competitors:
        parts.append(f"### Top {len(competitors)} Competing Pages\n")
        for i, comp in enumerate(competitors, 1):
            parts.append(f"**{i}. {comp['title']}**")
            parts.append(f"URL: {comp['url']}")
            for ex in comp.get("excerpts", [])[:3]:
                parts.append(f"  {ex[:3000]}")
            parts.append("")

    return "\n".join(parts)


def run_page_audit(page_url, queries, site_domain=None, max_queries=5):
    """Audit a page by researching its top queries against competitors."""
    client = _get_client()
    if client is None:
        return None

    audit_queries = queries[:max_queries]

    all_research = []
    with Progress(
        SpinnerColumn("dots"),
        TextColumn("[bold blue]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("Researching", total=len(audit_queries))
        for q in audit_queries:
            progress.update(task, description=f"Researching: {q[:50]}")
            data = research_query(q, own_page_url=page_url, site_domain=site_domain)
            all_research.append(data)
            progress.advance(task)

    context_parts = []
    for rd in all_research:
        context_parts.append(build_comparison_context(rd))

    return "\n---\n\n".join(context_parts)
