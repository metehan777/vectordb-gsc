import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

import config
import gsc_extractor
import data_processor
import vector_store
import ai_analyzer

console = Console()

BANNER = r"""
 ██████  ███████  ██████     ██    ██ ██████  
██       ██      ██          ██    ██ ██   ██ 
██   ███ ███████ ██          ██    ██ ██   ██ 
██    ██      ██ ██           ██  ██  ██   ██ 
 ██████  ███████  ██████       ████   ██████  
"""


def _parse_provider():
    if "--grok" in sys.argv:
        return "grok"
    if "--claude" in sys.argv:
        return "claude"
    return "gemini"


def print_banner():
    console.print(Text(BANNER, style="bold cyan"))
    console.print(
        Panel(
            "[bold white]Google Search Console[/bold white] data as a "
            "[bold magenta]Vector Database[/bold magenta], analyzed by "
            "[bold green]AI[/bold green]",
            border_style="dim",
            padding=(0, 2),
        )
    )
    console.print()


def print_help():
    print_banner()

    table = Table(
        box=box.ROUNDED, border_style="cyan",
        title="[bold]Available Commands[/bold]", title_style="bold white",
        show_header=True, header_style="bold cyan", padding=(0, 2),
    )
    table.add_column("Command", style="green", no_wrap=True)
    table.add_column("Description", style="white")

    table.add_row("extract", "Pull last 16 months of GSC data via API")
    table.add_row("process", "Process raw data and store embeddings in ChromaDB")
    table.add_row("refresh", "Extract + process in one step")
    table.add_row("analyze", "Interactive AI analysis session")
    table.add_row('ask "question"', "One-shot question (default: Gemini Flash)")
    table.add_row("", "")
    table.add_row('audit "url"', "Deep page audit: scrapes your page + competitors")
    table.add_row('compete "query"', "Competitor analysis: compares top results vs your data")
    table.add_row("", "")
    table.add_row("stats", "Show vector database statistics")
    table.add_row("help", "Show this help message")
    table.add_row("", "")
    table.add_row("[dim]Flags[/dim]", "[dim]--grok  --claude  (append to any analysis command)[/dim]")

    console.print(table)
    console.print()


def cmd_extract():
    print_banner()
    gsc_extractor.extract_all_data()


def cmd_process():
    print_banner()
    console.print(Panel("[bold]Step 1/2[/bold]  Processing raw data", border_style="blue"))
    query_docs, page_docs = data_processor.process_data()
    if query_docs is None:
        return
    console.print()
    console.print(Panel("[bold]Step 2/2[/bold]  Embedding & storing in ChromaDB", border_style="blue"))
    vector_store.store_all(query_docs, page_docs)
    console.print()
    _print_stats_inline()


def cmd_refresh():
    print_banner()
    console.print(Panel("[bold]Step 1/3[/bold]  Extracting GSC data", border_style="blue"))
    filepath = gsc_extractor.extract_all_data()
    if filepath is None:
        return
    console.print()
    console.print(Panel("[bold]Step 2/3[/bold]  Processing raw data", border_style="blue"))
    query_docs, page_docs = data_processor.process_data(filepath)
    if query_docs is None:
        return
    console.print()
    console.print(Panel("[bold]Step 3/3[/bold]  Embedding & storing in ChromaDB", border_style="blue"))
    vector_store.store_all(query_docs, page_docs)
    console.print()
    _print_stats_inline()


def cmd_analyze():
    print_banner()
    ai_analyzer.interactive_session()


def cmd_ask(question, provider="gemini"):
    print_banner()
    ai_analyzer.run_analysis("custom", provider=provider, custom_query=question)


def cmd_audit(page_url, provider="gemini"):
    print_banner()
    ai_analyzer.run_page_audit(page_url, provider=provider)


def cmd_compete(query, provider="gemini"):
    print_banner()
    ai_analyzer.run_competitor_analysis(query, provider=provider)


def cmd_stats():
    print_banner()
    _print_stats_inline()


def _print_stats_inline():
    stats = vector_store.get_collection_stats()
    qp = stats.get(config.QUERIES_COLLECTION, 0)
    pg = stats.get(config.PAGES_COLLECTION, 0)

    table = Table(
        box=box.ROUNDED, border_style="blue",
        title="[bold]ChromaDB Vector Store[/bold]", title_style="bold white",
        padding=(0, 2),
    )
    table.add_column("Collection", style="white", no_wrap=True)
    table.add_column("Documents", style="cyan", justify="right")
    table.add_column("Embedding Model", style="dim")

    table.add_row("Query-Page Pairs", f"{qp:,}", config.EMBEDDING_MODEL)
    table.add_row("Pages", f"{pg:,}", config.EMBEDDING_MODEL)
    table.add_row("", "", "")
    table.add_row("[bold]Total[/bold]", f"[bold]{qp + pg:,}[/bold]", f"{config.EMBEDDING_DIMENSIONS}d vectors")

    console.print(table)
    console.print()


def main():
    if len(sys.argv) < 2:
        print_help()
        return

    command = sys.argv[1].lower()

    simple_commands = {
        "extract": cmd_extract,
        "process": cmd_process,
        "refresh": cmd_refresh,
        "analyze": cmd_analyze,
        "stats": cmd_stats,
        "help": print_help,
    }

    if command in simple_commands:
        simple_commands[command]()
    elif command == "ask":
        if len(sys.argv) < 3:
            console.print("[bold red]Error:[/bold red] Please provide a question.")
            console.print('  [dim]Usage:[/dim] python main.py ask "your question"')
            return
        cmd_ask(sys.argv[2], _parse_provider())
    elif command == "audit":
        if len(sys.argv) < 3:
            console.print("[bold red]Error:[/bold red] Please provide a page URL.")
            console.print('  [dim]Usage:[/dim] python main.py audit "https://example.com/page"')
            return
        cmd_audit(sys.argv[2], _parse_provider())
    elif command == "compete":
        if len(sys.argv) < 3:
            console.print("[bold red]Error:[/bold red] Please provide a search query.")
            console.print('  [dim]Usage:[/dim] python main.py compete "your query"')
            return
        cmd_compete(sys.argv[2], _parse_provider())
    else:
        console.print(f"[bold red]Unknown command:[/bold red] {command}\n")
        print_help()


if __name__ == "__main__":
    main()
