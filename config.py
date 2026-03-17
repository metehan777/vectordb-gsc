import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

GSC_PROPERTY = os.getenv("GSC_PROPERTY", "")
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "service_account.json")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

EMBEDDING_MODEL = "gemini-embedding-2-preview"
EMBEDDING_DIMENSIONS = 768
GEMINI_MODEL = "gemini-3-flash-preview"
CLAUDE_MODEL = "claude-opus-4-6"

CHROMA_DB_PATH = "chroma_db"
RAW_DATA_DIR = "raw_data"

QUERIES_COLLECTION = "gsc_queries"
PAGES_COLLECTION = "gsc_pages"

EMBEDDING_BATCH_SIZE = 50
GSC_ROW_LIMIT = 25000

def get_date_range():
    end_date = datetime.now() - timedelta(days=3)
    start_date = end_date - timedelta(days=16 * 30)
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
