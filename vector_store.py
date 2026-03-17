import time
import chromadb
from google import genai
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn

import config

console = Console()

_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _gemini_client


def get_chroma_client():
    return chromadb.PersistentClient(path=config.CHROMA_DB_PATH)


def get_or_create_collection(client, name):
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def generate_embeddings(texts, batch_size=None):
    if batch_size is None:
        batch_size = config.EMBEDDING_BATCH_SIZE

    client = _get_gemini_client()
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        result = client.models.embed_content(
            model=config.EMBEDDING_MODEL,
            contents=batch,
            config={"output_dimensionality": config.EMBEDDING_DIMENSIONS},
        )
        all_embeddings.extend([e.values for e in result.embeddings])

        if i + batch_size < len(texts):
            time.sleep(0.5)

    return all_embeddings


def upsert_documents(collection, documents):
    batch_size = config.EMBEDDING_BATCH_SIZE

    with Progress(
        SpinnerColumn("dots"),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40, style="cyan", complete_style="bold green"),
        TaskProgressColumn(),
        TextColumn("[dim]|[/dim]"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task(
            f"Embedding → {collection.name}",
            total=len(documents),
        )

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            texts = [doc["text"] for doc in batch]
            ids = [doc["id"] for doc in batch]
            metadatas = [doc["metadata"] for doc in batch]

            embeddings = generate_embeddings(texts, batch_size=len(texts))

            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )
            progress.advance(task, advance=len(batch))


def query_collection(collection, query_text, n_results=10, where=None, where_document=None):
    embeddings = generate_embeddings([query_text])

    kwargs = {
        "query_embeddings": embeddings,
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where
    if where_document:
        kwargs["where_document"] = where_document

    return collection.query(**kwargs)


def store_all(query_docs, page_docs):
    client = get_chroma_client()

    if query_docs:
        queries_col = get_or_create_collection(client, config.QUERIES_COLLECTION)
        console.print(f"  [dim]Collection:[/dim] [cyan]{config.QUERIES_COLLECTION}[/cyan]  ({len(query_docs):,} documents)")
        upsert_documents(queries_col, query_docs)

    if page_docs:
        pages_col = get_or_create_collection(client, config.PAGES_COLLECTION)
        console.print(f"  [dim]Collection:[/dim] [cyan]{config.PAGES_COLLECTION}[/cyan]  ({len(page_docs):,} documents)")
        upsert_documents(pages_col, page_docs)

    console.print()
    console.print("  [bold green]All documents stored successfully.[/bold green]")


def get_collection_stats():
    client = get_chroma_client()
    stats = {}
    for name in [config.QUERIES_COLLECTION, config.PAGES_COLLECTION]:
        try:
            col = client.get_collection(name)
            stats[name] = col.count()
        except Exception:
            stats[name] = 0
    return stats
