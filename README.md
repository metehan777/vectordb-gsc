# GSC Vector Database

Turn your Google Search Console data into a vector database and analyze search performance with AI.

```
 ██████  ███████  ██████     ██    ██ ██████
██       ██      ██          ██    ██ ██   ██
██   ███ ███████ ██          ██    ██ ██   ██
██    ██      ██ ██           ██  ██  ██   ██
 ██████  ███████  ██████       ████   ██████
```

## What It Does

1. **Extracts** the last 16 months of search performance data from Google Search Console
2. **Embeds** queries, pages, and metrics into a local ChromaDB vector database using Gemini embeddings
3. **Analyzes** your data using AI with semantic retrieval (RAG) — pick from 3 providers
4. **Audits** individual pages by scraping your content + competitors via [Parallel.ai](https://parallel.ai/) and comparing what's missing

## Tech Stack

| Component | Tool | Cost |
|---|---|---|
| Vector Database | [ChromaDB](https://www.trychroma.com/) (local) | Free |
| Embeddings | [Gemini `gemini-embedding-2-preview`](https://ai.google.dev/gemini-api/docs/embeddings) (768d, MRL) | Free tier |
| Analysis LLM | [Gemini Flash 3](https://ai.google.dev/gemini-api/docs/models) | Free tier |
| Analysis LLM | [Grok 4.1](https://docs.x.ai/docs/models) (2M context window) | Pay-per-use |
| Analysis LLM | [Claude Opus](https://docs.anthropic.com/en/docs/about-claude/models) | Pay-per-use |
| Web Research | [Parallel.ai](https://parallel.ai/) Search + Extract API | Pay-per-use |
| Data Source | [Google Search Console API](https://developers.google.com/webmaster-tools/v1/api_reference_index) | Free |

### Why 3 LLM Providers?

| Provider | Context Window | Best For |
|---|---|---|
| **Gemini Flash 3** (default) | ~1M tokens | Fast, free analysis with good quality |
| **Grok 4.1** (`--grok`) | **2M tokens** | Deepest analysis — sends 5x more data from the vector DB |
| **Claude Opus** (`--claude`) | 200K tokens | Strategic, nuanced recommendations |

## Setup

### 1. Clone

```bash
git clone https://github.com/metehan777/vectordb-gsc.git
cd vectordb-gsc
pip install -r requirements.txt
```

### 2. Google Cloud Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Create a service account (or use an existing one)
3. Download the JSON key file and place it in the project root
4. Enable the **Search Console API** in your GCP project
5. In [Google Search Console](https://search.google.com/search-console), go to **Settings > Users and permissions** and add the service account email (e.g. `your-sa@project.iam.gserviceaccount.com`) as a user

### 3. API Keys

- **Gemini** (required): Free key at [Google AI Studio](https://aistudio.google.com/apikey)
- **Grok** (optional): Key at [xAI Console](https://console.x.ai/)
- **Claude** (optional): Key at [Anthropic Console](https://console.anthropic.com/)
- **Parallel** (optional): Key at [Parallel Platform](https://platform.parallel.ai/) — needed for `audit` and `compete` commands

### 4. Configure

```bash
cp .env.example .env
```

Edit `.env`:

```
SERVICE_ACCOUNT_FILE=your-service-account.json
GSC_PROPERTY=                  # leave blank to pick interactively
GEMINI_API_KEY=your-key
XAI_API_KEY=your-key           # optional, for Grok analysis
ANTHROPIC_API_KEY=your-key     # optional, for Claude analysis
PARALLEL_API_KEY=your-key      # optional, for page audit & competitor analysis
```

## Usage

### Extract Data

Pulls 16 months of GSC data (queries, pages, dates, countries, devices):

```bash
python main.py extract
```

If `GSC_PROPERTY` is blank, you'll see a property picker:

```
╭──────────────────────────────────────────────╮
│  #  Property URL                  Permission │
├──────────────────────────────────────────────┤
│  1  https://example.com/          siteOwner  │
│  2  sc-domain:example.org         siteOwner  │
╰──────────────────────────────────────────────╯
```

### Process & Embed

Aggregates raw rows into query-page pair documents, computes trends, and embeds everything into ChromaDB:

```bash
python main.py process
```

Or do both in one step:

```bash
python main.py refresh
```

### Analyze

Interactive session with 5 pre-built analyses + custom questions:

```bash
python main.py analyze
```

One-shot questions:

```bash
python main.py ask "which queries are rising fastest?"
python main.py ask "find cannibalization issues" --grok
python main.py ask "content gap analysis" --claude
```

### Page Audit (with Parallel.ai)

Scrapes your page + top-ranking competitors, combines with GSC data, and generates a detailed content gap audit:

```bash
python main.py audit "https://example.com/blog/my-post/" --grok
```

What it does:
1. Finds the top queries for that page from your GSC vector database
2. Scrapes your page content via Parallel.ai Extract API
3. Searches for competitor pages ranking for those same queries
4. Sends everything to the AI for a side-by-side comparison

### Competitor Analysis (with Parallel.ai)

Searches the web for any query and compares what competitors cover vs your site:

```bash
python main.py compete "perplexity ranking factors" --grok
```

### Stats

```bash
python main.py stats
```

## How It Works

```
GSC API ──→ Raw JSON ──→ Data Processor ──→ Gemini Embeddings ──→ ChromaDB
                                                                      │
                              AI Analysis (RAG) ←── Semantic Query ←──┘
                                 │                        │
                    Gemini / Grok / Claude        Parallel.ai Search
                                                  + Extract (optional)
```

1. **Extraction**: Pulls data month-by-month with pagination (25K rows per request) to handle large sites
2. **Processing**: Aggregates daily rows into query-page pairs with computed metrics (weighted avg position, CTR, trend classification)
3. **Embedding**: Uses `gemini-embedding-2-preview` with Matryoshka Representation Learning (MRL) at 768 dimensions
4. **Analysis**: Retrieves semantically relevant documents from ChromaDB, feeds them to an LLM with expert SEO system prompts. Grok receives 5x more context (200 docs vs 40) thanks to its 2M token window
5. **Web Research** (optional): For `audit` and `compete` commands, Parallel.ai scrapes live web content and competitor pages, giving the AI real data to compare against

## Why a Vector Database? (Honest Review)

GSC data is fundamentally **structured** — queries, pages, clicks, impressions, CTR, position, date. This is tabular data, and a SQL database would handle exact filtering and aggregations more precisely. So why use a vector database?

### What the Vector DB does well

- **Semantic discovery**: Ask "what content about AI is performing?" and it finds queries like "neural network tutorial" and "transformer architecture" — even though they don't contain the word "AI." SQL can't do that without manually building keyword lists.
- **Natural language interface**: Ask freeform questions and get contextually relevant data. No need to write SQL or build filters.
- **Cross-referencing patterns**: The embedding model surfaces connections between conceptually related queries that pure SQL filtering would miss.
- **Persistence**: Extract once from the GSC API, query locally thousands of times. No rate limits, no latency.

### Where the Vector DB is not ideal

- **Numerical precision is fuzzy**: When you ask "find queries with CTR below 2%", a SQL `WHERE ctr < 0.02` gives you the exact right rows. The vector DB does semantic text similarity — it might miss high-impression queries or include irrelevant ones because it's matching on text, not math.
- **Structured aggregations**: "Top 10 pages by clicks" is a trivial SQL query. With a vector DB, you're hoping the embedding similarity retrieves the right documents.
- **GSC data isn't unstructured text**: Vector DBs shine on documents, articles, and code. GSC metrics embedded as text like `"clicks: 150, impressions: 5000"` don't carry true numerical meaning in the vector space.

### What Parallel.ai adds

The `audit` and `compete` commands use [Parallel.ai](https://parallel.ai/) to scrape live web content — your own pages and competitor pages. This is where the tool goes beyond what any database (vector or SQL) or GSC MCP can do alone:

- **Your GSC data tells you *how* you rank** — clicks, impressions, position, CTR
- **Parallel.ai tells you *why* you rank (or don't)** — by scraping what's actually on your page vs. what competitors have

Neither a vector DB nor a SQL DB contains competitor content. Neither does the GSC API. Parallel.ai bridges that gap by giving the LLM real page content to compare against, turning a data analysis tool into a content strategy tool.

### Comparison: Vector DB vs GSC MCP vs SQL DB

| | Vector DB (this tool) | GSC MCP Server | SQL DB (DuckDB/SQLite) |
|---|---|---|---|
| **Data freshness** | Stale (needs `refresh`) | Real-time | Stale (needs import) |
| **Numeric precision** | Fuzzy (semantic similarity) | Exact (API filters) | Exact (`WHERE`, `ORDER BY`) |
| **Semantic search** | Yes | No | No |
| **Natural language queries** | Yes | No | No (needs NL-to-SQL layer) |
| **Historical analysis (16 months)** | Yes (all data stored locally) | Limited (API quotas per request) | Yes (all data stored locally) |
| **Bulk analysis speed** | Instant (local) | Slow (API calls per question) | Instant (local) |
| **Rate limits** | None (local) | GSC API quotas | None (local) |
| **Trend detection** | Yes (pre-computed) | No (raw API responses) | Possible (needs query logic) |
| **Web research / competitor scraping** | Yes (via Parallel.ai) | No | No |
| **Setup complexity** | Medium (embeddings cost time) | Low (just API credentials) | Low |
| **Best for** | Open-ended discovery + content audits | Quick live lookups | Precise metric filtering |

### The honest verdict

The **ideal architecture** would be a hybrid: SQL for precise numerical queries + vector DB for semantic discovery + LLM on top of both. This tool leans into the vector DB side, which makes it strong for exploratory analysis and natural language questions, but less precise for exact metric-based filtering. The real value isn't just the storage layer — it's the aggregation pipeline (`data_processor.py`) that computes trends, averages, and structures 2M+ raw rows into meaningful documents before anything touches the vector DB.

A GSC MCP server gives you live data but can't do bulk historical analysis, trend detection, or semantic search. If you only need "what's my CTR for query X today?", an MCP is simpler. If you want "which topic clusters are declining across 16 months and what should I do about it?", you need what this tool provides.

Where this tool truly differentiates is the **Parallel.ai integration**: no other approach gives you side-by-side content comparison between your pages and competitors, combined with 16 months of GSC performance data, all fed into an LLM in one prompt.

## Embedding Model

Uses `gemini-embedding-2-preview` with MRL (Matryoshka Representation Learning). The model outputs 3072-dimensional embeddings by default, truncated to 768 dimensions via `output_dimensionality` for efficient storage with minimal quality loss. You can adjust this in `config.py` to 1536 or 3072 if needed.

## Project Structure

```
├── main.py              # CLI entrypoint
├── config.py            # Configuration and environment variables
├── gsc_extractor.py     # GSC API extraction with service account auth
├── data_processor.py    # Raw data aggregation and trend computation
├── vector_store.py      # ChromaDB + Gemini embedding operations
├── ai_analyzer.py       # RAG analysis with Gemini Flash / Grok / Claude
├── web_research.py      # Parallel.ai web search & page scraping
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
└── .gitignore
```

## License

MIT
