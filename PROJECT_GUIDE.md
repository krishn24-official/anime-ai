# AnimeAI (AniVerse): Technical Architecture & Defense Guide

---

## 1. Executive Summary & Project Purpose

**AnimeAI** (AniVerse) is an asynchronous entertainment intelligence platform that unifies fragmented pop-culture data—spanning anime series, manga volumes, movies, television series, voice actors, character relationships, fictional organizations, real-time syndicated entertainment news, and narrative world lore—into a queryable knowledge graph and conversational AI engine.

The backend is developed with **FastAPI** (Python 3.11+) and backed by a hybrid **MongoDB Atlas** cluster combining polymorphic document collections with dense vector search. Rather than functioning as a simplistic wrapper around an LLM, the system implements:
1. **Autonomous Tool-Calling Agent (`/agent`)**: A multi-turn reasoning agent powered by Google Gemini (`gemini-2.5-flash`) with 9 registered database tools and automated intent dispatch.
2. **Conversational Assistant (`/chat`)**: A low-latency conversational engine featuring multimodal image recognition, intent keyword resolution (e.g. family/rival relationships), and grounded RAG over deep series lore.
3. **PDF Lore Ingestion & RAG Pipeline (`/admin/lore`)**: In-memory PDF parsing via `pypdf`, structural markdown header normalization, semantic chunking with sibling merge guards, local 384-dimensional vector embedding via `SentenceTransformer("all-MiniLM-L6-v2")`, and vector retrieval via MongoDB Atlas Vector Search.
4. **Tri-Pillar Trending Engine (`/content/trending`)**: Continuous real-time ranking driven by user search spike logs, automated RSS news entity mentions, and admin-pinned Editor's Picks.
5. **Automated Ingestion Workers**: Scheduled background ingestion from AniList GraphQL, TMDb v3, OMDb, and 13 syndicated RSS feeds using `APScheduler`.

---

## 2. System Architecture & Request Flow

```
                                      +------------------------------------+
                                      |     React / Vite Frontend (FE)     |
                                      +------------------------------------+
                                                        |
                                             HTTPS / REST / WebSocket (/ws)
                                                        v
+----------------------------------------------------------------------------------------------------------+
|                                           FASTAPI APPLICATION                                            |
|                                                                                                          |
|  [ Middleware ]: CORS (Localhost, Capacitor Android/iOS, Tauri Desktop, Vercel)                         |
|  [ Authentication & Security ]: JWT Bearer Guards (HS256, 15m access, 30d refresh TTL, Prod Enforced)     |
|  [ WebSocket Manager ]: Real-time news notifications with offline client catch-up                        |
|                                                                                                          |
|  [ 25 Mounted API Routers (app/api/router.py) ]:                                                         |
|    /characters    /relationships  /anime       /manga      /health     /home       /events    /search    |
|    /chat          /news           /auth        /movies     /tv-series  /content    /agent     /game      |
|    /tier-list     /admin/news     /orgs        /admin/content /actors  /admin/actors /voice-actors       |
|    /admin/lore (Upload, Delete, Status)                                                                  |
+----------------------------------------------------------------------------------------------------------+
       |                  |                    |                  |                     |
       v                  v                    v                  v                     v
+--------------+  +----------------+  +------------------+  +---------------+  +------------------+
| Repositories |  | Domain Logic   |  | RAG Engine (Lore)|  | Agent Runtime |  | Background Tasks |
| (Async Motor |  |   (Services)   |  |                  |  | (9 Tools)     |  |  (APScheduler)    |
| 30 Modules)  |  +----------------+  +------------------+  +---------------+  +------------------+
+--------------+          |                    |                  |                     |
       |                  |                    |                  |                     |
       |                  v                    |                  |                     |
       |          +-----------------+          |                  |                     |
       |          | Sentence Trans. | <--------+                  |                     |
       |          | all-MiniLM-L6-v2|                             |                     |
       |          | (384-dim local) |                             |                     |
       |          +-----------------+                             |                     |
       |                  |                                       v                     |
       |                  |                             +--------------------+          |
       |                  |                             | Google Gemini API  |          |
       |                  |                             | (gemini-2.5-flash) |          |
       |                  |                             +--------------------+          |
       v                  v                                                             v
+------------------------------------+                                  +-----------------------+
|        MONGODB ATLAS CLUSTER       |                                  |   EXTERNAL APIS & RSS  |
|                                    |                                  +-----------------------+
|  Collections:                      |                                  | - AniList GraphQL     |
|   - anime, manga, characters       |                                  | - TMDb (v3 API)       |
|   - movies, tv_series, actors      |                                  | - OMDb API            |
|   - voice_actors, organizations    |                                  | - Cloudinary CDN      |
|   - lore_chunks (Atlas Vector Idx) |                                  | - 13 RSS Syndication  |
|   - relationships, news, users     |                                  |   Feeds (ANN, CR, MAL,|
|   - comments, tier_lists, trending |                                  |   Variety, THR, etc.) |
|   - trending_mentions, search_logs |                                  +-----------------------+
+------------------------------------+
```

### End-to-End Request Lifecycles

#### Flow A: PDF Lore Upload & Grounded RAG Ingestion (`/admin/lore`)
1. **Upload**: Admin client posts a PDF to `POST /admin/lore/upload` with form parameters `series_id` and optional `character_ids`. Guarded by `get_current_admin`.
2. **Extraction**: `lore_service.process_lore_pdf` reads in-memory bytes using `pypdf.PdfReader`.
3. **Normalization**: `normalize_markdown_spacing()` applies regex lookbehinds (`(?<![\n#])(#{1,4}\s+)`, `(?<!\n)(---|\*\*\*)\s*`, `(?<!\n)(\s*[-*+]\s+)`) to unglue headers, horizontal rules, and bullet points merged during PDF stream extraction.
4. **Hierarchical Chunking**:
   - If markdown headings exist, `chunk_markdown_text()` parses sections into a heading tree, attaches hierarchical breadcrumb strings (e.g. `Titan Origins > The Nine Titans > The Attack Titan`), applies `_is_safe_merge_target` sibling guards, and merges undersized sibling fragments.
   - If non-markdown, recursive character splitting (`chunk_text`) splits content on `["\n\n", "\n", ". ", " ", ""]` within configured bounds (`LORE_CHUNK_SIZE=800`, `LORE_CHUNK_OVERLAP=100`).
5. **Local Vector Embedding**: `LoreEmbedder` embeds chunk text with local PyTorch model `SentenceTransformer("all-MiniLM-L6-v2")`, outputting 384-dimensional normalized vectors.
6. **Persistence**: Chunks are stored in MongoDB `lore_chunks`. Atlas Search Vector Index (`lore_vector_index`) indexes the vectors with cosine similarity.
7. **Query Retrieval & Grounding**: When a lore question is processed (`POST /chat` or agent tool `query_lore`), the query is embedded, Atlas `$vectorSearch` retrieves the top `K=5` chunks, and Gemini synthesizes an answer strictly grounded by `LORE_SYSTEM_PROMPT` (defined at `app/services/gemini_service.py:120`), which prohibits inventing details outside the provided context.

#### Flow B: Autonomous Tool-Calling Agent (`POST /agent`)
1. **User Request**: User sends message to `POST /agent`.
2. **Intent Pre-Routing**: `agent_service.py` evaluates `INTENT_PATTERNS` regex rules for quick queries (birthdays, anniversaries, recent news, content trends).
3. **Model Loop**: If dynamic reasoning is required, Gemini (`gemini-2.5-flash`) is invoked with `AGENT_SYSTEM_PROMPT` and 9 declared tool signatures:
   - `get_today_birthdays`: Characters celebrating birthdays today.
   - `get_today_events`: Anime and manga airing/publishing anniversaries today.
   - `get_latest_news`: Recent entertainment news across categories.
   - `get_news_by_category`: News filtered by category (`Anime`, `Games`, `Movies`, `TV Series`).
   - `search_content`: Multi-collection search across characters, anime, manga, movies, and TV series.
   - `get_character_info`: Detailed character profile, abilities, and relationships with fuzzy suggestions.
   - `get_content_trends`: Highest-rated or most-watchlisted media.
   - `get_organization_info`: Fictional groups, pirate crews, clans, and affiliations.
   - `query_lore`: Narrative spoilers, backstories, and deep plot details via vector RAG.
4. **Execution & Feedback**: In an async loop capped at `MAX_ITERATIONS = 5`, `execute_tool()` dispatches calls against MongoDB repositories and returns structured JSON back to Gemini until a final synthesized response is returned.

#### Flow C: Tri-Pillar Trending Engine (`/content/trending`)
1. **Pillar 1 — User Search Spikes**: `recompute_search_trending()` runs every 30 minutes. It aggregates search queries from `search_logs` within the last 3 hours. Content exceeding `MIN_SEARCH_THRESHOLD = 15` searches or a `RELATIVE_MULTIPLIER = 2.0` spike is written to `trending` with reason `"Searched by X people"`.
2. **Pillar 2 — Automated News Mentions**: `recompute_news_trending()` runs every 30 minutes. During RSS pipeline runs, `title_matcher.py` scans ingested article text against cached entity aliases and logs hits to `trending_mentions`. Entities with high mention counts over the last 48 hours are upserted into `trending` with reason `"Mentioned in X articles"`.
3. **Pillar 3 — Manual Editor's Pick**: Admins can invoke `set_manual_trending()`, assigning `score = 1000.0`, `pinned = True`, and uploading an optional custom banner to Cloudinary (`entertainment_hub/trending`).
4. **Output**: The collection is queried with sort `{"pinned": -1, "score": -1}` to power the homepage banner and trending feed.

---

## 3. Directory & File Reference Map

```
anime_ai/
├── app/
│   ├── api/
│   │   ├── deps.py                  # Auth dependencies (get_current_user, get_current_admin)
│   │   ├── router.py                # Aggregator mounting 25 domain routers
│   │   └── routes/                  # Individual route handlers
│   ├── backend/
│   │   ├── ingestion/               # AniList GraphQL, TMDb client, and 13 RSS feed scrapers
│   │   ├── transformers/            # Entity data transformers
│   │   └── utils/
│   │       └── slug.py              # Canonical create_slug() function
│   ├── db/
│   │   ├── index_utils.py           # Safe index creation wrapper (create_index_safely)
│   │   ├── indexes.py               # Collection index definitions & Atlas Vector Search spec
│   │   ├── init_db.py               # Database ping & health verification
│   │   ├── mongo.py                 # Async Motor client, connect_db, get_db, close_db
│   │   └── setup_collections.py     # Initial schema validation and collections setup
│   ├── repositories/                # Async MongoDB CRUD repositories (30 modules)
│   ├── schemas/                     # Pydantic request/response validation schemas
│   ├── services/                    # Business logic, AI agents, RAG, schedulers (64 modules)
│   ├── utils/                       # General helpers
│   ├── config.py                    # Environment settings & production security guards
│   └── main.py                      # FastAPI app instance, CORS, WebSockets, on_event hooks
├── tests/                           # Pytest integration & unit test suite (24 files)
├── pytest.ini                       # Pytest configuration with test loop scopes & flags
└── .env.example                     # Environment template
```

### Core Application Files

| Path | Primary Responsibility | Key Functions / Classes | Collaborators / Callers |
| :--- | :--- | :--- | :--- |
| `app/main.py` | App entry point, CORS config, `/ws` endpoint, startup/shutdown events | `app`, `startup()`, `shutdown()`, `websocket_endpoint()` | Uvicorn, API Routers, Schedulers |
| `app/config.py` | Environment configuration & production security validation | `MONGO_URI`, `JWT_SECRET_KEY`, `LORE_CHUNK_SIZE`, guard | All app modules |
| `app/api/deps.py` | FastAPI endpoint dependency guards | `get_current_user()`, `get_current_admin()` | Protected routes in `app/api/routes` |
| `app/api/router.py` | Central router registering all 25 sub-routers | `api_router` | `app/main.py` |
| `app/db/mongo.py` | Async Motor client connection lifecycle | `connect_db()`, `close_db()`, `get_db()`, `get_client()` | `app/main.py`, Repositories |
| `app/db/indexes.py` | Standard B-Tree, compound, unique, and text indexes | `create_indexes()` | `app/main.py` (startup) |
| `app/backend/utils/slug.py` | General-purpose string slugification | `create_slug(text)` | Ingestion services, Repositories |

### Key API Routes (`app/api/routes/`)

| Path | Primary Responsibility | Key Endpoints | Auth Requirements |
| :--- | :--- | :--- | :--- |
| `admin_lore.py` | Lore document management (**exactly 3 routes**) | `POST /admin/lore/upload`, `DELETE /admin/lore/{series_id}`, `GET /admin/lore/{series_id}/status` | Admin (`get_current_admin`) |
| `agent.py` | Autonomous AI agent execution | `POST /agent` | Public |
| `chat.py` | Conversational assistant with image support | `POST /chat` | Public |
| `content.py` | Unified search, trending, ratings, and watchlists | `GET /content/trending`, `GET /content/{type}/{id}` | Public / User for ratings |
| `auth.py` | User registration, login, token refresh, OTP | `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh` | Public |
| `admin_content.py`| Manual CRUD for anime, movies, TV series, episodes | `POST /admin/content/{type}`, `PUT /admin/content/{type}/{id}` | Admin |
| `admin_actors.py` | Actor synchronization and manual creation | `POST /admin/actors/sync-tmdb`, `POST /admin/actors` | Admin |
| `admin_news.py` | Manual news article publishing and deletion | `POST /admin/news`, `DELETE /admin/news/{id}` | Admin |

### Key Domain Services (`app/services/`)

| Path | Primary Responsibility | Key Functions / Classes | Collaborators / Callers |
| :--- | :--- | :--- | :--- |
| `agent_service.py` | Agent tool-calling loop & intent pre-router | `run_agent()`, `INTENT_PATTERNS`, `MAX_ITERATIONS` | `app/api/routes/agent.py` |
| `agent_tool_definitions.py`| 9 Gemini tool declarations & system prompt | `AGENT_TOOLS`, `AGENT_SYSTEM_PROMPT` | `agent_service.py` |
| `agent_tools.py` | Concrete async execution of tool calls | `execute_tool()`, `tool_get_character_info()` | `agent_service.py` |
| `chat_service.py` | Deterministic intent routing & chat context builder | `process_chat_message()`, `TARGET_RELATIONSHIP_INTENTS` | `app/api/routes/chat.py` |
| `gemini_service.py`| Google GenAI client wrapper & system prompts | `ask_gemini_with_lore()`, `LORE_SYSTEM_PROMPT` (L120) | `chat_service.py`, `agent_service.py` |
| `lore_service.py` | PDF extraction, markdown chunking, local embedding | `process_lore_pdf()`, `normalize_markdown_spacing()`, `LoreEmbedder` | `admin_lore.py`, `chat_service.py` |
| `trending_service.py`| Search log spike analysis & news mention ranking | `set_manual_trending()`, `recompute_search_trending()` | `news_scheduler.py`, Admin routes |
| `news_pipeline_service.py`| Multi-source RSS ingestion, extraction, entity match | `run_news_pipeline()`, `SOURCES` (13 scrapers) | `news_scheduler.py` |
| `news_scheduler.py`| APScheduler job orchestrator (30m / 24h intervals) | `start_news_scheduler()`, `stop_news_scheduler()` | `app/main.py` |
| `daily_discovery_service.py`| Multi-year TMDb movie/TV discovery & AniList sync | `run_daily_discovery()` | `news_scheduler.py` |
| `cast_reconciliation_service.py`| TMDb cast reconciliation, actor deduplication | `reconcile_cast()`, `resolve_or_create_actor()` | Discovery & Ingestion services |
| `relationship_admin_service.py`| Bidirectional character relationship graph builder | `build_relationship_pair()`, `_slug()`, `_make_rel_id()` | Admin content routes |

---

## 4. Technology & Model Inventory

| Technology / Component | Version / Specification | Role in System | Architectural Rationale |
| :--- | :--- | :--- | :--- |
| **FastAPI** | `>=0.115.0` | Primary Asynchronous Web API | Native `asyncio` concurrency, strict Pydantic model validation, auto-generated OpenAPI. |
| **Motor (Async PyMongo)**| `>=3.6.0` | Asynchronous MongoDB Driver | Non-blocking event loop execution during heavy multi-collection queries. |
| **Google Gemini 2.5 Flash** | `gemini-2.5-flash` | Primary LLM (Agent & Chat) | Sub-second inference latency, large context window, native tool-calling schema compatibility. |
| **Google GenAI SDK** | `google-genai` | Official Google AI Client | Direct integration with Gemini function calling and multimodal vision payloads. |
| **Sentence-Transformers** | `all-MiniLM-L6-v2` | Dense Lore Embedding Model | Local CPU inference (no external API cost or latency), 384-dimensional dense semantic vectors. |
| **MongoDB Atlas Vector Search** | Dimension: `384`, Metric: `cosine` | Dense Vector Index (`lore_vector_index`) | Eliminates external vector databases (Pinecone/Milvus); colocates vectors with relational document filters. Configured in MongoDB Atlas. |
| **APScheduler** | `3.10.x` (`AsyncIOScheduler`) | In-Process Task Scheduler | Lightweight periodic execution for news ingestion (every 30m) and discovery (every 24h) without Redis. |
| **PyPDF** | `pypdf` | PDF Document Text Extraction | Pure-Python stream extraction of in-memory PDF bytes without external binary C-dependencies. |
| **Trafilatura** | `2.0.x` | Web Article Body Extraction | Cleans HTML to text from RSS links, stripping boilerplate, ads, and navigation chrome. |
| **Cloudinary SDK** | `1.41.x` | Media Asset Storage & CDN | Offloads user-uploaded images and custom trending banners from backend disk storage. |

---

## 5. Data Model & Key Collections

All documents adhere to a strict, prefixed primary key naming standard:

| Collection Name | Prefix Standard | Purpose | Key Indexed Fields |
| :--- | :--- | :--- | :--- |
| `anime` | `anime_<slug>` | AniList anime TV, movies, OVAs | `_id`, `slug`, `title.english`, `title.romaji`, `genres`, `status` |
| `manga` | `manga_<slug>` | Manga, light novels, one-shots | `_id`, `slug`, `name`, `genres`, `status` |
| `characters` | `char_<slug>` | Character profiles across anime & manga | `_id`, `name`, `name (text)`, `birth_month`, `birth_day`, `game_properties` |
| `voice_actors` | `va_<slug>` | Japanese & English voice actors | `_id`, `name` |
| `movies` | `movie_<tmdb_id>`| TMDb live-action & animated films | `_id`, `tmdb_id`, `title`, `release_date`, `is_adult` |
| `tv_series` | `tv_<tmdb_id>` | TMDb television series | `_id`, `tmdb_id`, `title`, `first_air_date`, `seasons` |
| `actors` | `actor_<tmdb_id>`| TMDb live-action cast & crew | `_id`, `tmdb_id`, `name`, `is_deleted` |
| `organizations` | `org_<slug>` | Fictional factions, clans, pirate crews | `_id`, `name`, `type`, `anime_ids`, `manga_id` |
| `lore_chunks` | Auto ObjectID / hash | Chunked lore texts with 384-dim embeddings | `_id`, `series_id`, `character_ids`, `embedding_vector` (Atlas Vector Index) |
| `relationships` | `rel_<src>_<tgt>_<type>`| Character relations (family, rival, ally)| `_id`, `source_id`, `target_id`, `relationship` |
| `news` | Auto hash / slug | Syndicated media news articles | `_id`, `url` (unique), `published_at`, `category`, `source` |
| `trending` | Composite / type+id | Active trending feed entries | `content_type`, `content_id` (unique), `pinned`, `score`, `expires_at` (TTL) |
| `trending_mentions` | Composite / mention | RSS article entity mention logs | `content_id`, `news_id` (unique), `matched_at` (TTL 48h) |
| `search_logs` | Auto ObjectID | User search query telemetry | `content_id`, `searched_at` (TTL 3h) |
| `users` | Auto ObjectID | User accounts & permissions | `_id`, `email` (unique), `username` (unique), `is_admin`, `password_hash` |
| `refresh_tokens` | Auto ObjectID | JWT refresh tokens | `token` (unique), `user_id`, `expires_at` (MongoDB TTL index) |

### Clarification on Slug Functions

The codebase uses two distinct slug functions for different purposes:
1. **`create_slug(text: str)`** in `app/backend/utils/slug.py`:
   - Generic system-wide slugifier used across ingestion and content creation.
   - Converts arbitrary string titles to lowercase and substitutes non-alphanumeric characters with underscores (`re.sub(r"[^a-z0-9]+", "_", text).strip("_")`).
2. **`_slug(text: str)`** in `app/services/relationship_admin_service.py`:
   - Specialized relationship ID helper.
   - Takes existing character `_id` strings (e.g. `char_naruto_uzumaki`), strips the `"char_"` prefix, and strips punctuation so that `_make_rel_id(source_id, target_id, rel)` produces clean composite IDs (e.g. `rel_naruto_uzumaki_sasuke_uchiha_rival`).
3. *(Note: There is no `make_slug` in the codebase; any earlier reference was an erroneous naming assumption).*

---

## 6. Security, Authentication & Safety Guards

1. **JWT Secret Enforcement & Production Fallback Guard (`app/config.py`)**:
   - Authentication relies on HS256 JWT tokens (15-minute access expiry, 30-day refresh token stored in MongoDB with a TTL auto-delete index).
   - In production or when running on Render (`os.getenv("ENVIRONMENT") == "production" or os.getenv("RENDER")`), `app/config.py` raises a `RuntimeError` on startup if `JWT_SECRET_KEY` is empty or left as the default `"dev-secret-change-me"`.
2. **Test Database Isolation Guard (`tests/conftest.py`)**:
   - The test fixture inspects `MONGO_DB_NAME` before executing tests. If the database name does not contain `"test"`, the runner immediately raises a `RuntimeError("Refusing to run tests against non-test database: ...")` to protect production and staging data.
3. **Debug Endpoint Removal**:
   - The development debugging route `/debug-db` has been permanently removed from `app/main.py`. The frontend repository was scanned to confirm zero references exist.
4. **Adult Content Ingestion Guards**:
   - **AniList**: Ingestion requests enforce `isAdult: false` in GraphQL variables, and parser scripts (`fetch_all.py`, `fetch_animes.py`, `fetch_manga.py`) reject entries containing the `"Hentai"` genre.
   - **TMDb**: The client (`tmdb_client.py`) includes `include_adult="false"` on outbound calls; synchronizers verify `if details.get("adult") is True` to skip adult movies and TV shows; repositories filter with `{"is_adult": {"$ne": True}}`.
   - **Cast/Actors**: Ingestion scripts exclude performers flagged with `adult: true`.

---

## 7. Architectural Decisions & Tradeoffs

1. **Local MiniLM Embedding vs. Remote Cloud Embeddings (e.g. OpenAI / Google)**
   - *Decision*: Embed lore locally using `all-MiniLM-L6-v2`.
   - *Rationale*: Eliminates third-party embedding API costs, removes external rate limit dependencies, provides sub-millisecond local inference, and guarantees deterministic 384-dimensional vector representations.
   - *Tradeoff*: Increases memory usage by ~100MB on cold start for PyTorch model weights.

2. **MongoDB Atlas Vector Search vs. Dedicated Vector DB (Pinecone/Milvus)**
   - *Decision*: Colocate vector index inside MongoDB Atlas.
   - *Rationale*: Single database cluster for both relational graph documents and vector embeddings. Eliminates distributed synchronization issues and allows filtering by `series_id` and `character_ids` natively during `$vectorSearch`.
   - *Tradeoff*: Atlas Vector Search indexes are managed in the Atlas UI or Atlas Admin API and index documents asynchronously via Lucene.

3. **In-Process APScheduler vs. Celery + Redis**
   - *Decision*: Run periodic ingestion tasks inside FastAPI via `AsyncIOScheduler`.
   - *Rationale*: Zero infrastructure overhead—no Redis broker or Celery worker fleet to monitor for a single-server deployment.
   - *Tradeoff*: Tasks run in the same process; scaling to multiple Uvicorn workers requires a distributed job lock or dedicated worker container.

4. **Multi-Tool Autonomous Agent vs. Prompt Context Stuffing**
   - *Decision*: Expose 9 distinct domain tools to Gemini with parameter schemas.
   - *Rationale*: Prevents prompt token blowup, reduces hallucination, and ensures that the LLM only receives precise documents fetched from MongoDB.

---

## 8. Real-World Bug Log & Production Solutions

### 1. Extracted PDF Heading Gluing
- **Issue**: Ingested lore documents frequently missed section headers, causing large portions of the text to be treated as a single unformatted block.
- **Root Cause**: `pypdf` extracted text streams where line breaks between visual bounding boxes were omitted, resulting in lines like `"Backstory#### Levi Ackerman"`. Standard regex (`^#{1,4}\s+`) failed to match because the `#` symbols were not at the start of a line.
- **Solution**: Developed `normalize_markdown_spacing()` using regex lookbehinds (`(?<![\n#])(#{1,4}\s+)`) that unglue headings, horizontal rules, and bullet points while preserving valid multi-hash headings like `###`.

### 2. Sibling Fragment Fragmentation in Markdown Chunking
- **Issue**: Very short sub-headings (e.g. `### Status: Alive`) created tiny 20-character chunks that polluted vector search results with low-information vectors.
- **Root Cause**: Section chunking split aggressively on every heading without considering minimum section length.
- **Solution**: Implemented `merge_small_sections()` with a sibling safety guard (`_is_safe_merge_target()`). Tiny sections are buffered and merged forward only if the subsequent section shares the same parent breadcrumb path and heading hierarchy.

### 3. Upcoming Movie Horizon & Remake Title Collisions
- **Issue**: Announced blockbusters (e.g. *Avengers: Doomsday*) and reboots (e.g. *Ghost Rider*) were either missed or skipped during daily discovery.
- **Root Cause**: Discovery enforced a 120-day cutoff, and movie ingestion skipped records if an existing movie had the same title.
- **Solution**: Expanded the discovery horizon up to 4 years without restrictive release type filters, and allowed distinct TMDB IDs and release years to index into unique slugs (e.g. `movie_ghost_rider_1`).

### 4. Stale Test Suite Contracts
- **Issue**: 17 tests in the baseline test suite failed or errored during automated testing.
- **Root Cause**: Test fixtures used outdated assumptions—such as passing BSON `ObjectId` instead of string `_id` to episode repositories, asserting deprecated upcoming function names, expecting synchronous returns from async profile formatters, and hardcoding older Gemini model names.
- **Solution**: Updated test assertions to match valid active contracts without deleting tests, verifying zero regressions across all admin, news, chat, and gemini suites.

---

## 9. Local Setup & Execution Guide

### 1. Environment Configuration
Create a `.env` file in the root directory:
```env
MONGO_URI=mongodb+srv://<username>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority
MONGO_DB_NAME=anime_ai
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL_NAME=gemini-2.5-flash
TMDB_API_KEY=...
OMDB_API_KEY=...
JWT_SECRET_KEY=test-jwt-secret-key-32-chars-long-for-testing
ENVIRONMENT=development
```

### 2. Starting the Backend Server
```powershell
python -m uvicorn app.main:app --reload --port 8000
```

### 3. Running Test Suites
```powershell
python -m pytest tests/ -s
```

### 4. Atlas Vector Search Index Configuration
In MongoDB Atlas, navigate to **Atlas Search & Vector Search** on the `lore_chunks` collection and create index `lore_vector_index`:
```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding_vector",
      "numDimensions": 384,
      "similarity": "cosine"
    },
    {
      "type": "filter",
      "path": "series_id"
    },
    {
      "type": "filter",
      "path": "character_ids"
    }
  ]
}
```

---

## 10. Technical Interview Defense: Questions & Live Code Changes

### Question 1: "Why use MongoDB instead of PostgreSQL + pgvector for this architecture?"
> **Answer**: "The domain model spans highly heterogeneous entities—anime with romaji/native titles and air seasons, TMDb movies with crew departments and box office numbers, fictional organizations, and syndicated news articles. MongoDB's polymorphic document model accommodates these schema variations natively without requiring complex relational joins across 15 nullable tables. Furthermore, MongoDB Atlas Vector Search colocates vector embeddings with full-text search and document fields, enabling efficient compound filtering (`series_id`, `character_ids`) in a single `$vectorSearch` pipeline."

### Question 2: "How do you prevent the autonomous agent from hallucinating or entering infinite loops?"
> **Answer**: "We constrain the agent execution loop in `agent_service.py` with three distinct guardrails:
> 1. An explicit safety cap (`MAX_ITERATIONS = 5`), breaking immediately if the model exceeds 5 turns.
> 2. Strict tool parameter schemas that reject malformed arguments before querying the database.
> 3. For narrative lore, `LORE_SYSTEM_PROMPT` in `gemini_service.py` strictly instructs the model to answer using only the provided context and to state explicitly if an event or detail is not mentioned."

### Question 3: "How does the platform handle adult/NSFW content during ingestion?"
> **Answer**: "Adult filtering is enforced at the network ingestion boundary:
> 1. **AniList**: We pass `isAdult: false` directly in GraphQL queries and verify that `"Hentai"` is excluded from the `genres` array.
> 2. **TMDb**: We append `include_adult="false"` to all outbound requests and check `if details.get("adult") is True` before storing records.
> 3. **Cast/Actors**: Ingestion routines inspect the `adult` boolean to filter adult industry performers."

---

### Live Coding Scenarios: 5-Minute Changes

#### Scenario A: "Add a new tool to the `/agent` endpoint (e.g., search anime by genre)."
- **Files to touch**: `app/services/agent_tool_definitions.py`, `app/services/agent_tools.py`
- **Steps**:
  1. Add tool definition `search_anime_by_genre` to `AGENT_TOOLS` with parameter `genre: string`.
  2. Implement `async def tool_search_anime_by_genre(genre: str)` in `agent_tools.py` querying `anime_repository`.
  3. Register mapping in `execute_tool()`: `"search_anime_by_genre": tool_search_anime_by_genre`.

#### Scenario B: "Adjust Lore chunk size or overlap for RAG retrieval."
- **Files to touch**: `.env` or `app/config.py`
- **Steps**:
  1. Set `LORE_CHUNK_SIZE = 1000` and `LORE_CHUNK_OVERLAP = 150` in `.env` (or update default values in `app/config.py`).
  2. Restart the application and re-upload the PDF lore via `POST /admin/lore/upload`.

#### Scenario C: "Add a ping endpoint or health check."
- **Files to touch**: `app/api/routes/health.py`
- **Steps**:
  1. Add `@router.get("/ping")` returning `{"status": "pong"}`.

---

## 11. Two-Minute Live Demo Script

1. **System Health & Connectivity**:
   - `GET http://localhost:8000/health`
   - *Demonstrates*: MongoDB connection is active and responsive.
2. **Autonomous Tool-Calling Agent**:
   - `POST http://localhost:8000/agent` with payload `{"message": "Who voices Naruto Uzumaki, and are there any news articles about them?"}`
   - *Demonstrates*: Gemini invokes `get_character_info`, retrieves the voice actor, calls `get_latest_news`, and synthesizes a comprehensive response.
3. **Conversational Assistant & Lore Grounding**:
   - `POST http://localhost:8000/chat` with a question about an uploaded series lore document.
   - *Demonstrates*: Vector RAG retrieval from `lore_chunks` grounded by `LORE_SYSTEM_PROMPT`.
4. **Real-Time News Ingestion & WebSockets**:
   - `GET http://localhost:8000/news/latest?limit=5` and connect to `ws://localhost:8000/ws`.
   - *Demonstrates*: Automated background RSS pipeline syncing 13 entertainment news sources with real-time push notifications.
