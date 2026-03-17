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
