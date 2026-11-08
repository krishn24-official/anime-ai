import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "anime_ai")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-lite")

# ── OMDb ──────────────────────────────────────────────
OMDB_API_KEY = os.getenv("OMDB_API_KEY")
OMDB_BASE_URL = "https://www.omdbapi.com/"

# ── TMDb ──────────────────────────────────────────────
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE_URL = "https://api.tmdb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p"

# ── Cloudinary ────────────────────────────────────────
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# ── Auth (JWT) ────────────────────────────────────────
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-me")
if os.getenv("ENVIRONMENT") == "production" or os.getenv("RENDER"):
    if not JWT_SECRET_KEY or JWT_SECRET_KEY == "dev-secret-change-me":
        raise RuntimeError(
            "CRITICAL SECURITY: JWT_SECRET_KEY must be set in production / Render environment! Refusing to start with insecure default."
        )
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "15"))  # 15 minutes
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))  # 30 days

# ── Gmail SMTP ────────────────────────────────────────
GMAIL_SENDER = os.getenv("GMAIL_SENDER")  # your Gmail address
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")  # Gmail App Password
OTP_EXPIRE_MINUTES = 10

# ── RAG / Lore Retrieval ──────────────────────────────
LORE_CHUNK_SIZE = int(os.getenv("LORE_CHUNK_SIZE", "800"))
LORE_CHUNK_OVERLAP = int(os.getenv("LORE_CHUNK_OVERLAP", "100"))
LORE_EMBEDDING_MODEL = os.getenv("LORE_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
# Compare news headlines by meaning (reuses the lore embedding model, which then
# stays loaded). Set to "false" on hosts short on memory: word matching still runs.
NEWS_SEMANTIC_DEDUP = os.getenv("NEWS_SEMANTIC_DEDUP", "true").lower() != "false"
LORE_TOP_K = int(os.getenv("LORE_TOP_K", "5"))
LORE_VECTOR_INDEX_NAME = os.getenv("LORE_VECTOR_INDEX_NAME", "lore_vector_index")

# ── Global search ─────────────────────────────────────
# "auto":  Atlas Search on `search_catalog` when its index is ready, else regex.
# "regex": always use regex search on the source collections (no catalog upkeep).
SEARCH_BACKEND = os.getenv("SEARCH_BACKEND", "auto").strip().lower()
# Hours between full rebuilds of `search_catalog` (catches ingestion/TMDb sync changes).
SEARCH_CATALOG_REBUILD_HOURS = int(os.getenv("SEARCH_CATALOG_REBUILD_HOURS", "6"))
# Kinds indexed in the Atlas catalog; other kinds use regex search. Actors are left
# out by default: ~177k rows would more than double the catalog's storage.
SEARCH_CATALOG_KINDS = tuple(
    k.strip()
    for k in os.getenv(
        "SEARCH_CATALOG_KINDS", "anime,movies,tv_series,manga,characters,organizations"
    ).split(",")
    if k.strip()
)
# Cluster storage quota (MB) the catalog build must stay under (Atlas M0 = 512).
ATLAS_STORAGE_LIMIT_MB = int(os.getenv("ATLAS_STORAGE_LIMIT_MB", "512"))
