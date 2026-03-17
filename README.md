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
3. **Analyzes** your data using AI (Gemini Flash 3 or Claude Opus) with semantic retrieval (RAG)

## Tech Stack

Everything runs locally, all tools are free-tier:

| Component | Tool | Cost |
|---|---|---|
| Vector Database | [ChromaDB](https://www.trychroma.com/) (local) | Free |
| Embeddings | [Gemini `gemini-embedding-2-preview`](https://ai.google.dev/gemini-api/docs/embeddings) (768d, MRL) | Free tier |
| Analysis LLM | [Gemini Flash 3](https://ai.google.dev/gemini-api/docs/models) | Free tier |
| Analysis LLM (alt) | [Claude Opus](https://docs.anthropic.com/en/docs/about-claude/models) | Pay-per-use |
| Data Source | [Google Search Console API](https://developers.google.com/webmaster-tools/v1/api_reference_index) | Free |

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

- Get a free Gemini API key at [Google AI Studio](https://aistudio.google.com/apikey)
- (Optional) Get an Anthropic API key at [Anthropic Console](https://console.anthropic.com/)

### 4. Configure

```bash
cp .env.example .env
```

Edit `.env`:

```
SERVICE_ACCOUNT_FILE=your-service-account.json
GSC_PROPERTY=                  # leave blank to pick interactively, or set e.g. https://example.com/
GEMINI_API_KEY=your-key
ANTHROPIC_API_KEY=your-key     # optional, for Claude analysis
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

```
╭─────── Analyses ────────────────────────────────────────────╮
│   1  Performance Overview    Top queries, pages, trends     │
│   2  Opportunity Finder      High-impression, low-CTR       │
│   3  Declining Queries       Queries losing position        │
│   4  Content Gap Analysis    Pages not matching intent      │
│   5  Cannibalization Check   Competing pages for same query │
│   6  Custom Query            Ask anything                   │
╰─────────────────────────────────────────────────────────────╯
```

One-shot questions:

```bash
python main.py ask "which queries are rising fastest?"
python main.py ask "find cannibalization issues" --claude
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
                                 │
                          Gemini Flash 3 / Claude Opus
```

1. **Extraction**: Pulls data month-by-month with pagination (25K rows per request) to handle large sites
2. **Processing**: Aggregates daily rows into query-page pairs with computed metrics (weighted avg position, CTR, trend classification)
3. **Embedding**: Uses `gemini-embedding-2-preview` with Matryoshka Representation Learning (MRL) at 768 dimensions for efficient storage
4. **Analysis**: Retrieves semantically relevant documents from ChromaDB, then feeds them to an LLM with expert SEO system prompts

## Embedding Model

Uses `gemini-embedding-2-preview` with MRL (Matryoshka Representation Learning). The model outputs 3072-dimensional embeddings by default, truncated to 768 dimensions via `output_dimensionality` for efficient storage with minimal quality loss. You can adjust this in `config.py` to 1536 or 3072 if needed.

## Project Structure

```
├── main.py              # CLI entrypoint
├── config.py            # Configuration and environment variables
├── gsc_extractor.py     # GSC API extraction with service account auth
├── data_processor.py    # Raw data aggregation and trend computation
├── vector_store.py      # ChromaDB + Gemini embedding operations
├── ai_analyzer.py       # RAG analysis with Gemini Flash / Claude Opus
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
└── .gitignore
```

## License

MIT
