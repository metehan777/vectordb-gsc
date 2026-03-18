from openai import OpenAI
from google import genai
from anthropic import Anthropic
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich import box

import config
import vector_store
import web_research

console = Console()

YEAR_CONTEXT = "The current year is 2026. Base all analysis, trends, and recommendations on this timeframe."
NO_SCHEMA = "Do NOT suggest schema markup, structured data, or JSON-LD unless the user explicitly asks about schema."

ANALYSIS_PROMPTS = {
    "overview": {
        "title": "Performance Overview",
        "description": "Top queries, pages, and overall trends",
        "query_text": "top performing queries pages clicks impressions",
        "system": (
            f"You are an expert SEO analyst. {YEAR_CONTEXT} {NO_SCHEMA} "
            "Analyze the Google Search Console data provided. "
            "Give a comprehensive performance overview including:\n"
            "1. Top performing queries and pages by clicks\n"
            "2. Overall traffic trends (rising, declining, stable)\n"
            "3. Key metrics summary (total clicks, impressions, avg CTR, avg position)\n"
            "4. Notable patterns or anomalies\n"
            "Use specific numbers from the data. Be concise but thorough."
        ),
        "n_results": 50,
    },
    "opportunities": {
        "title": "Opportunity Finder",
        "description": "High-impression, low-CTR queries to optimize",
        "query_text": "high impressions low CTR opportunity optimize",
        "system": (
            f"You are an expert SEO analyst. {YEAR_CONTEXT} {NO_SCHEMA} "
            "Analyze the Google Search Console data provided. "
            "Find and prioritize SEO opportunities by identifying:\n"
            "1. Queries with high impressions but low CTR (below 3%) - these need title/description optimization\n"
            "2. Queries ranking in positions 5-20 that could move to page 1 with content improvements\n"
            "3. Queries with declining trends that need attention\n"
            "For each opportunity, explain WHY it's an opportunity and WHAT action to take. "
            "Prioritize by potential impact (impressions x possible CTR improvement)."
        ),
        "n_results": 50,
        "where": {"position": {"$gte": 5}},
    },
    "declining": {
        "title": "Declining Queries",
        "description": "Queries losing position or clicks over time",
        "query_text": "declining falling dropping traffic loss position",
        "system": (
            f"You are an expert SEO analyst. {YEAR_CONTEXT} {NO_SCHEMA} "
            "Analyze the Google Search Console data provided. "
            "Focus on declining performance:\n"
            "1. Identify queries and pages with declining trends\n"
            "2. Quantify the decline (position changes, click/impression drops)\n"
            "3. Group declining queries by topic or page\n"
            "4. Suggest recovery strategies for each group\n"
            "5. Prioritize by severity and potential traffic recovery\n"
            "Be specific with numbers and actionable in recommendations."
        ),
        "n_results": 50,
        "where": {"trend": "declining"},
    },
    "content_gaps": {
        "title": "Content Gap Analysis",
        "description": "Queries where pages don't match intent",
        "query_text": "content gap mismatch query page relevance",
        "system": (
            f"You are an expert SEO analyst. {YEAR_CONTEXT} {NO_SCHEMA} "
            "Analyze the Google Search Console data provided. "
            "Perform a content gap analysis:\n"
            "1. Find queries where the ranking page doesn't seem like the best match\n"
            "2. Identify query clusters that lack dedicated content\n"
            "3. Find queries with high impressions but very low clicks (possible content mismatch)\n"
            "4. Suggest new content pieces or page optimizations\n"
            "5. Identify topics where competitors likely have better content\n"
            "Provide specific, actionable content recommendations."
        ),
        "n_results": 50,
    },
    "cannibalization": {
        "title": "Cannibalization Check",
        "description": "Multiple pages competing for same queries",
        "query_text": "same query multiple pages cannibalization competing",
        "system": (
            f"You are an expert SEO analyst. {YEAR_CONTEXT} {NO_SCHEMA} "
            "Analyze the Google Search Console data provided. "
            "Detect keyword cannibalization:\n"
            "1. Find queries where multiple pages from the same site are ranking\n"
            "2. Assess which page is the 'right' one for each cannibalized query\n"
            "3. Quantify the impact (split clicks/impressions between pages)\n"
            "4. Recommend consolidation strategies (redirect, merge, differentiate)\n"
            "5. Prioritize fixes by traffic impact\n"
            "Look at the page URLs and query patterns carefully to detect overlap."
        ),
        "n_results": 50,
    },
}

CUSTOM_SYSTEM = (
    f"You are an expert SEO analyst with access to Google Search Console data. {YEAR_CONTEXT} {NO_SCHEMA} "
    "Answer the user's question using the data provided. Be specific with numbers, "
    "identify patterns, and give actionable recommendations."
)

PROVIDER_LABELS = {
    "gemini": "[bold blue]Gemini Flash[/bold blue]",
    "claude": "[bold magenta]Claude Opus[/bold magenta]",
    "grok": "[bold red]Grok 4.1[/bold red]",
}

GROK_N_RESULTS = 400

PAGE_AUDIT_SYSTEM = (
    f"You are an expert SEO content strategist. {YEAR_CONTEXT} {NO_SCHEMA} "
    "You are given:\n"
    "1. Google Search Console data showing how a page performs (queries, clicks, impressions, CTR, positions)\n"
    "2. The actual content of the user's page (scraped from the web)\n"
    "3. The content of top-ranking competitor pages for the same queries\n\n"
    "Perform a thorough page audit:\n"
    "1. **Content Coverage Gap**: What topics/subtopics do competitors cover that this page is missing?\n"
    "2. **Heading Structure**: Compare H1/H2/H3 structure against competitors\n"
    "3. **Depth Analysis**: Where does the page lack depth compared to top results?\n"
    "4. **Search Intent Match**: Does the page content match what users are actually searching for (based on GSC queries)?\n"
    "5. **Quick Wins**: Specific sections, paragraphs, or data points to add that competitors have\n"
    "6. **Internal Linking**: Missing internal links or structural improvements\n\n"
    "Be extremely specific. Reference actual content from both the user's page and competitors. "
    "Provide a prioritized action list with estimated impact."
)

COMPETITOR_GAP_SYSTEM = (
    f"You are an expert SEO analyst specializing in competitive analysis. {YEAR_CONTEXT} {NO_SCHEMA} "
    "You are given:\n"
    "1. Google Search Console data for the user's site\n"
    "2. Live search results from the web showing what competitors rank for\n\n"
    "Analyze the competitive landscape:\n"
    "1. **Ranking Competitors**: Who are the main competitors appearing for these queries?\n"
    "2. **Content Superiority**: What makes competitor content better (format, depth, freshness, media)?\n"
    "3. **Missing Topics**: What are competitors covering that the user's site doesn't have at all?\n"
    "4. **Differentiation Opportunities**: Where can the user create unique value competitors lack?\n"
    "5. **Actionable Plan**: Specific content pieces to create or update, with priority order\n\n"
    "Be specific with URLs, topics, and recommendations."
)


def _gather_context(analysis_key, custom_query=None, large_context=False):
    """Retrieve relevant documents from ChromaDB for the analysis."""
    client = vector_store.get_chroma_client()
    queries_col = vector_store.get_or_create_collection(client, config.QUERIES_COLLECTION)
    pages_col = vector_store.get_or_create_collection(client, config.PAGES_COLLECTION)

    if custom_query:
        query_text = custom_query
        n_results = GROK_N_RESULTS if large_context else 40
        where = None
    else:
        prompt_config = ANALYSIS_PROMPTS[analysis_key]
        query_text = prompt_config["query_text"]
        n_results = GROK_N_RESULTS if large_context else prompt_config.get("n_results", 30)
        where = prompt_config.get("where")

    vdb_table = Table(box=box.SIMPLE, border_style="dim", padding=(0, 1))
    vdb_table.add_column("Parameter", style="white")
    vdb_table.add_column("Value", style="cyan")
    vdb_table.add_row("Semantic query", f'"{query_text}"')
    vdb_table.add_row("Max results (queries)", str(n_results))
    page_n = min(n_results, 100) if large_context else min(n_results, 100)
    vdb_table.add_row("Max results (pages)", str(page_n))
    if where:
        vdb_table.add_row("Filter", str(where))
    console.print(Panel(
        vdb_table,
        title="[bold]Vector DB Query[/bold]",
        border_style="blue",
        padding=(0, 1),
    ))

    query_results = vector_store.query_collection(
        queries_col, query_text, n_results=n_results, where=where
    )
    page_results = vector_store.query_collection(
        pages_col, query_text, n_results=page_n
    )

    q_count = len(query_results["documents"][0]) if query_results and query_results["documents"] else 0
    p_count = len(page_results["documents"][0]) if page_results and page_results["documents"] else 0
    console.print(f"  [dim]Retrieved[/dim] [cyan]{q_count}[/cyan] [dim]query-page pairs and[/dim] [cyan]{p_count}[/cyan] [dim]page docs from vector DB[/dim]\n")

    context_parts = ["## Query-Page Performance Data\n"]
    if query_results and query_results["documents"]:
        for doc in query_results["documents"][0]:
            context_parts.append(f"- {doc}")

    context_parts.append("\n## Page-Level Performance Data\n")
    if page_results and page_results["documents"]:
        for doc in page_results["documents"][0]:
            context_parts.append(f"- {doc}")

    stats = vector_store.get_collection_stats()
    context_parts.append(f"\n## Database Stats")
    context_parts.append(f"Total query-page pairs in database: {stats.get(config.QUERIES_COLLECTION, 0):,}")
    context_parts.append(f"Total pages in database: {stats.get(config.PAGES_COLLECTION, 0):,}")

    return "\n".join(context_parts)


def analyze_with_gemini(system_prompt, context, user_message=None):
    client = genai.Client(api_key=config.GEMINI_API_KEY)

    prompt = f"{system_prompt}\n\n---\n\nHere is the search performance data:\n\n{context}"
    if user_message:
        prompt += f"\n\n---\n\nUser's specific question: {user_message}"

    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
    )
    parts = response.candidates[0].content.parts
    return "".join(p.text for p in parts if p.text)


def analyze_with_claude(system_prompt, context, user_message=None):
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

    max_ctx_chars = 80000
    if len(context) > max_ctx_chars:
        context = context[:max_ctx_chars] + "\n\n[... truncated for context window ...]"

    user_content = f"Here is the search performance data:\n\n{context}"
    if user_message:
        user_content += f"\n\n---\n\nUser's specific question: {user_message}"

    try:
        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.content[0].text
    except Exception as e:
        console.print(f"  [yellow]Claude API error: {e}[/yellow]")
        console.print("  [yellow]Falling back to Gemini...[/yellow]\n")
        return analyze_with_gemini(system_prompt, context, user_message)


def analyze_with_grok(system_prompt, context, user_message=None):
    client = OpenAI(
        api_key=config.XAI_API_KEY,
        base_url=config.XAI_BASE_URL,
    )

    user_content = f"Here is the search performance data:\n\n{context}"
    if user_message:
        user_content += f"\n\n---\n\nUser's specific question: {user_message}"

    try:
        response = client.chat.completions.create(
            model=config.GROK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            max_tokens=4096,
        )
        return response.choices[0].message.content
    except Exception as e:
        console.print(f"  [yellow]Grok API error: {e}[/yellow]")
        console.print("  [yellow]Falling back to Gemini...[/yellow]\n")
        return analyze_with_gemini(system_prompt, context, user_message)


def run_analysis(analysis_key, provider="gemini", custom_query=None):
    if analysis_key == "custom":
        if not custom_query:
            console.print("  [red]Please provide a question for custom analysis.[/red]")
            return None
        system_prompt = CUSTOM_SYSTEM
        title = "Custom Analysis"
    else:
        prompt_config = ANALYSIS_PROMPTS.get(analysis_key)
        if not prompt_config:
            console.print(f"  [red]Unknown analysis type: {analysis_key}[/red]")
            return None
        system_prompt = prompt_config["system"]
        title = prompt_config["title"]

    provider_label = PROVIDER_LABELS.get(provider, provider)
    large_context = provider == "grok"
    console.print()

    context = _gather_context(analysis_key, custom_query, large_context=large_context)

    with Live(
        Panel(
            f"  Generating analysis with {provider_label}..."
            + (" [dim](2M context — sending more data)[/dim]" if large_context else ""),
            border_style="dim",
            padding=(1, 2),
        ),
        console=console,
        transient=True,
    ):
        if provider == "grok":
            result = analyze_with_grok(system_prompt, context, custom_query)
        elif provider == "claude":
            result = analyze_with_claude(system_prompt, context, custom_query)
        else:
            result = analyze_with_gemini(system_prompt, context, custom_query)

    console.print(Panel(
        Markdown(result),
        title=f"[bold white]{title}[/bold white]  [dim]via {provider}[/dim]",
        border_style="green",
        padding=(1, 3),
    ))
    return result


def _dispatch_llm(provider, system_prompt, context, user_message=None):
    """Route to the right LLM provider."""
    if provider == "grok":
        return analyze_with_grok(system_prompt, context, user_message)
    elif provider == "claude":
        return analyze_with_claude(system_prompt, context, user_message)
    return analyze_with_gemini(system_prompt, context, user_message)


def run_page_audit(page_url, provider="gemini"):
    """Audit a specific page: scrape it + competitors, combine with GSC data."""
    console.print()
    provider_label = PROVIDER_LABELS.get(provider, provider)

    console.print(Panel(
        f"  Page: [bold cyan]{page_url}[/bold cyan]\n"
        f"  AI:   {provider_label}\n\n"
        "  [dim]This will scrape your page, search for competitors on your top queries,\n"
        "  and compare content to find what's missing.[/dim]",
        title="[bold]Page Audit[/bold]",
        border_style="blue",
        padding=(1, 2),
    ))
    console.print()

    client = vector_store.get_chroma_client()
    queries_col = vector_store.get_or_create_collection(client, config.QUERIES_COLLECTION)

    vdb_table = Table(box=box.SIMPLE, border_style="dim", padding=(0, 1))
    vdb_table.add_column("Parameter", style="white")
    vdb_table.add_column("Value", style="cyan")
    vdb_table.add_row("Semantic query", f'"{page_url}"')
    vdb_table.add_row("Max results", "100")
    vdb_table.add_row("Filter", f'{{"page": "{page_url}"}}')
    console.print(Panel(vdb_table, title="[bold]Vector DB Query — Page Lookup[/bold]", border_style="blue", padding=(0, 1)))

    page_results = vector_store.query_collection(
        queries_col, page_url, n_results=100,
        where={"page": page_url},
    )

    top_queries = []
    if page_results and page_results["metadatas"]:
        pairs = []
        for meta in page_results["metadatas"][0]:
            pairs.append((meta.get("query", ""), meta.get("impressions", 0)))
        pairs.sort(key=lambda x: x[1], reverse=True)
        top_queries = [q for q, _ in pairs[:5] if q]

    q_found = len(page_results["metadatas"][0]) if page_results and page_results["metadatas"] else 0
    console.print(f"  [dim]Retrieved[/dim] [cyan]{q_found}[/cyan] [dim]matching docs[/dim]")

    if not top_queries:
        console.print("  [yellow]No queries found for this page in the vector database.[/yellow]")
        console.print("  [dim]Falling back to page URL as search query.[/dim]")
        top_queries = [page_url.split("/")[-2].replace("-", " ") if "/" in page_url else page_url]

    console.print(f"  Top queries to research: [cyan]{', '.join(top_queries)}[/cyan]\n")

    site_domain = config.GSC_PROPERTY or None
    web_context = web_research.run_page_audit(
        page_url, top_queries, site_domain=site_domain, max_queries=5
    )

    if not web_context:
        console.print("  [red]Web research failed. Check PARALLEL_API_KEY in .env[/red]")
        return None

    gsc_context = _gather_context(
        None, custom_query=" ".join(top_queries), large_context=(provider == "grok")
    )
    full_context = f"{gsc_context}\n\n---\n\n{web_context}"

    console.print()
    with Live(
        Panel(f"  Generating audit with {provider_label}...", border_style="dim", padding=(1, 2)),
        console=console, transient=True,
    ):
        result = _dispatch_llm(provider, PAGE_AUDIT_SYSTEM, full_context)

    console.print(Panel(
        Markdown(result),
        title=f"[bold white]Page Audit: {page_url}[/bold white]  [dim]via {provider}[/dim]",
        border_style="green",
        padding=(1, 3),
    ))
    return result


def run_competitor_analysis(query, provider="gemini"):
    """Search the web for a query and compare against our GSC data."""
    console.print()
    provider_label = PROVIDER_LABELS.get(provider, provider)

    console.print(Panel(
        f"  Query: [bold cyan]{query}[/bold cyan]\n"
        f"  AI:    {provider_label}\n\n"
        "  [dim]Searching the web for top-ranking pages and comparing with your data.[/dim]",
        title="[bold]Competitor Analysis[/bold]",
        border_style="blue",
        padding=(1, 2),
    ))
    console.print()

    site_domain = config.GSC_PROPERTY or None
    competitors = web_research.search_competitors(query, site_domain=site_domain, max_results=5)

    if not competitors:
        console.print("  [red]Web search failed. Check PARALLEL_API_KEY in .env[/red]")
        return None

    web_parts = [f"## Live Web Results for: \"{query}\"\n"]
    for i, comp in enumerate(competitors, 1):
        web_parts.append(f"**{i}. {comp['title']}**")
        web_parts.append(f"URL: {comp['url']}")
        for ex in comp.get("excerpts", [])[:3]:
            web_parts.append(f"  {ex[:4000]}")
        web_parts.append("")
    web_context = "\n".join(web_parts)

    gsc_context = _gather_context(None, custom_query=query, large_context=(provider == "grok"))
    full_context = f"{gsc_context}\n\n---\n\n{web_context}"

    with Live(
        Panel(f"  Generating competitor analysis with {provider_label}...", border_style="dim", padding=(1, 2)),
        console=console, transient=True,
    ):
        result = _dispatch_llm(provider, COMPETITOR_GAP_SYSTEM, full_context)

    console.print(Panel(
        Markdown(result),
        title=f"[bold white]Competitor Analysis: {query}[/bold white]  [dim]via {provider}[/dim]",
        border_style="green",
        padding=(1, 3),
    ))
    return result


def interactive_session():
    stats = vector_store.get_collection_stats()
    total = sum(stats.values())
    if total == 0:
        console.print(Panel(
            "No data in vector database.\n\n"
            "Run [bold green]python main.py process[/bold green] first.",
            title="[bold red]Empty Database[/bold red]",
            border_style="red",
        ))
        return

    db_info = Table.grid(padding=(0, 2))
    db_info.add_column(style="dim")
    db_info.add_column(style="cyan bold")
    db_info.add_row("Query-page pairs:", f"{stats.get(config.QUERIES_COLLECTION, 0):,}")
    db_info.add_row("Pages:", f"{stats.get(config.PAGES_COLLECTION, 0):,}")
    db_info.add_row("Embedding model:", config.EMBEDDING_MODEL)
    console.print(Panel(db_info, title="[bold]Vector Database[/bold]", border_style="blue", padding=(1, 3)))
    console.print()

    analyses = list(ANALYSIS_PROMPTS.items())
    menu = Table(
        box=box.SIMPLE,
        show_header=False,
        padding=(0, 2),
        show_edge=False,
    )
    menu.add_column(style="bold cyan", width=4, justify="right")
    menu.add_column(style="bold white")
    menu.add_column(style="dim")

    for i, (key, val) in enumerate(analyses, 1):
        menu.add_row(str(i), val["title"], val["description"])
    menu.add_row(str(len(analyses) + 1), "Custom Query", "Ask anything about your search data")
    menu.add_row("0", "Exit", "")

    console.print(Panel(menu, title="[bold]Analyses[/bold]", border_style="cyan", padding=(1, 2)))
    console.print(
        "  [dim]Tip: type a question directly, or append a flag to pick the AI provider:[/dim]\n"
        "        [bold]--grok[/bold]  [dim]Grok 4.1 (2M context)[/dim]   "
        "[bold]--claude[/bold]  [dim]Claude Opus[/dim]   "
        "[dim](default: Gemini Flash)[/dim]\n"
    )

    while True:
        try:
            choice = console.input("  [bold white]>[/bold white] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n  [dim]Goodbye.[/dim]")
            break

        if not choice:
            continue
        if choice == "0":
            console.print("  [dim]Goodbye.[/dim]")
            break

        provider = "gemini"
        for flag, prov in [(" --grok", "grok"), (" --claude", "claude")]:
            if choice.lower().endswith(flag):
                provider = prov
                choice = choice[: -len(flag)].strip()
                break

        try:
            idx = int(choice)
            if idx == 0:
                console.print("  [dim]Goodbye.[/dim]")
                break
            if 1 <= idx <= len(analyses):
                key = analyses[idx - 1][0]
                run_analysis(key, provider=provider)
            elif idx == len(analyses) + 1:
                question = console.input("  [bold]Your question:[/bold] ").strip()
                if question:
                    run_analysis("custom", provider=provider, custom_query=question)
            else:
                console.print("  [yellow]Invalid choice.[/yellow]")
        except ValueError:
            run_analysis("custom", provider=provider, custom_query=choice)

        console.print()
