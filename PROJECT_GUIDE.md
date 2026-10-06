# AnimeAI: Comprehensive Technical Architecture & Defense Guide

---

## 1. Executive Summary & Project Purpose

**AnimeAI** is a production-grade multimodal anime and pop-culture intelligence platform designed to unify scattered entertainment data—spanning anime series, manga volumes, movies, live-action adaptations, voice actors, character relationships, and real-time entertainment news—into a queryable knowledge graph and conversational AI engine. 

The backend is built on **FastAPI** (Python 3.11+) and backed by a hybrid **MongoDB Atlas** cluster combining relational-style document graphs with dense vector search. Rather than functioning as a standard wrapper around an LLM, the system implements an autonomous, tool-calling reasoning agent (`/agent`), a low-latency conversational assistant (`/chat`), and an end-to-end RAG (Retrieval-Augmented Generation) pipeline for custom lore documents and PDF world guides. 

Real-time media feeds from AniList GraphQL, TMDb, OMDb, and five syndicated RSS feeds are continually ingested and deduplicated by background scheduler workers. The result is a unified platform capable of answering complex lore queries, tracing cross-franchise voice actor timelines, summarizing current industry events, and hosting interactive user communities (tier lists, watchlists, reviews, and community threads).

---

## 2. System Architecture & Request Flow

```
                                      +------------------------------------+
                                      |     React / Vite Frontend (FE)     |
                                      +------------------------------------+
                                                        |
                                            HTTPS / REST / WebSocket
                                                        v
+----------------------------------------------------------------------------------------------------------+
|                                           FASTAPI APPLICATION                                            |
|                                                                                                          |
|  [ Middleware ]: CORS | Rate Limiting | JWT Authentication | Global Error & Exception Handlers           |
|                                                                                                          |
|  [ API Layer / Routers ]:                                                                                |
|    /auth     /anime      /manga       /characters  /lore       /agent      /chat      /news              |
|    /movies   /tv-series  /actors      /voice-actor /tier-lists /watchlist  /admin     /comments          |
+----------------------------------------------------------------------------------------------------------+
       |                  |                    |                  |                     |
       v                  v                    v                  v                     v
+--------------+  +----------------+  +------------------+  +---------------+  +------------------+
| Repositories |  |  Domain Logic  |  | RAG Engine (Lore)|  | Agent Runtime |  | Background Tasks |
| (Async Motor |  |   (Services)   |  |                  |  | (Tool Calling)|  |  (APScheduler)    |
|  CRUD layer) |  +----------------+  +------------------+  +---------------+  +------------------+
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
|   - lore_chunks (Vector Index)     |                                  | - Cloudinary (Media)  |
|   - relationships, news, users     |                                  | - RSS Feeds (ANN,     |
|   - comments, tier_lists, trending |                                  |   Crunchyroll, etc.)  |
+------------------------------------+                                  +-----------------------+
```

### End-to-End Request Lifecycles

1. **RAG Lore Upload & Retrieval Lifecycle**:
   - `User -> POST /lore/upload (PDF/Markdown)` -> `lore_service.py` extracts text via `pypdf`.
   - Text is cleaned with regex (`normalize_markdown_spacing`), chunked using structural markdown headers and token limits (500 tokens, 100 token overlap).
   - Each chunk is embedded locally via `SentenceTransformer("all-MiniLM-L6-v2")` into a 384-dimensional dense vector.
   - Chunks are stored in MongoDB Atlas `lore_chunks` collection with index `lore_vector_index`.
   - Query: `User -> POST /lore/query` -> Query vector generated -> Atlas `$vectorSearch` runs cosine similarity with metadata filters (`franchise_id`, `canon_tier`) -> Relevant chunks injected into Gemini context -> Grounded answer returned with citations.

2. **Autonomous Tool-Calling Agent Lifecycle**:
   - `User -> POST /agent` -> `agent_service.py` builds system prompt and registers 7 native python tool declarations.
   - Gemini (`gemini-2.5-flash`) inspects intent and emits tool calls (e.g., `search_anime_database(query="Gojo Satoru")`, `find_voice_actor(character_name="Gojo Satoru")`).
   - The application executes the respective repository queries asynchronously against MongoDB.
   - Tool outputs are fed back to Gemini as `ToolResponseMessage` until Gemini synthesizes the final comprehensive answer.

---

## 3. Directory & File Reference Map

### Core Application (`app/`)

| Path | Primary Responsibility | Key Functions / Classes | Collaborators / Callers |
| :--- | :--- | :--- | :--- |
| `app/main.py` | Application entry point, lifespan management, CORS, scheduler startup | `lifespan()`, `create_app()` | Uvicorn, API Routers, Scheduler |
| `app/api/router.py` | Central API router aggregator registering all sub-routers | `api_router` | `app/main.py` |
| `app/core/config.py` | Centralized environment configuration via Pydantic Settings | `Settings` | All services, DB, Auth |
| `app/core/security.py` | Password hashing (bcrypt) and JWT encode/decode routines | `create_access_token()`, `verify_password()`, `hash_password()` | `auth_service.py`, `dependencies.py` |
| `app/core/dependencies.py` | FastAPI endpoint dependency injection (Auth guards) | `get_current_user()`, `get_current_admin()` | Protected routes across `/api/routes` |

### Database Layer (`app/db/`)

| Path | Primary Responsibility | Key Functions / Classes | Collaborators / Callers |
| :--- | :--- | :--- | :--- |
| `app/db/mongo.py` | Asynchronous Motor client setup, connection lifecycle, DB accessors | `connect_db()`, `close_db()`, `get_db()`, `get_client()` | Lifespan, Repositories, Services |
| `app/db/indexes.py` | Compound, unique, and text index definitions across all collections | `create_indexes()` | `app/main.py` (lifespan initialization) |
| `app/db/setup_collections.py` | Initial collection creation and validation schemas | `create_collections()` | `app/main.py` |

### Repositories Layer (`app/repositories/`)

| Path | Primary Responsibility | Key Functions / Classes | Collaborators / Callers |
| :--- | :--- | :--- | :--- |
| `anime_repository.py` | CRUD, pagination, filtering, and text search for anime collection | `get_anime_by_id()`, `list_anime()`, `search_anime()` | `anime_service.py` |
| `character_repository.py`| Character queries, voice actor linking, name search | `get_character_by_id()`, `search_characters()` | `character_service.py` |
| `lore_repository.py` | Lore chunk persistence and Atlas vector search queries | `insert_chunks()`, `vector_search_chunks()` | `lore_service.py` |
| `news_repository.py` | Media news article queries, category filtering, search | `get_latest_news()`, `search_news_articles()` | `news_service.py` |
| `user_repository.py` | User account persistence, profile updates, credentials | `find_by_email()`, `create_user()`, `update_user()` | `auth_service.py` |
| `movie_repository.py` | TMDb movie documents CRUD and search | `get_movie_by_id()`, `list_movies()` | `movie_service.py` |
| `tv_repository.py` | TMDb television series queries and season tracking | `get_tv_by_id()`, `list_tv()` | `tv_service.py` |
| `actor_repository.py` | Live-action and voice actor queries | `get_actor_by_id()`, `search_actors()` | `actor_service.py` |
| `watchlist_repository.py`| User bookmarking and watch status management | `add_to_watchlist()`, `get_user_watchlist()` | `watchlist_service.py` |
| `tierlist_repository.py` | User custom tier lists persistence | `create_tier_list()`, `get_tier_lists()` | `tierlist_service.py` |

### Domain Services Layer (`app/services/`)

| Path | Primary Responsibility | Key Functions / Classes | Collaborators / Callers |
| :--- | :--- | :--- | :--- |
| `agent_service.py` | Autonomous multi-step tool-calling agent with 7 domain tools | `run_agent()`, `TOOL_DECLARATIONS` | `app/api/routes/agent.py` |
| `chat_service.py` | Low-latency streaming conversational RAG over media graph | `chat_stream()`, `build_chat_context()` | `app/api/routes/chat.py` |
| `lore_service.py` | PDF parsing, chunking, local embedding, and vector retrieval | `ingest_lore_file()`, `retrieve_relevant_chunks()` | `app/api/routes/lore.py` |
| `gemini_client.py` | Centralized Google GenAI SDK wrapper and model invocations | `generate_text()`, `generate_chat()` | Agent, Chat, Lore services |
| `embedding_service.py` | Local PyTorch `SentenceTransformer` vector inference | `get_embedding()`, `embed_text()` | `lore_service.py` |
| `news_pipeline_service.py`| Multi-source RSS aggregation, HTML scraping, deduplication | `run_news_pipeline()`, `_fetch_all_sources()` | Scheduler (`app/main.py`) |
| `daily_discovery_service.py`| TMDb / AniList daily release status and change sync | `run_daily_discovery()` | Scheduler (`app/main.py`) |
| `tmdb_sync_service.py` | TMDb synchronization for movies, TV series, and actors | `sync_movie()`, `sync_tv()`, `sync_actor()` | Discovery service, Admin routes |
| `duplicate_detection_service.py`| Cross-collection duplicate detection and safe merge guards | `check_for_duplicate()`, `_is_safe_merge_target()` | Ingestion pipelines |

### Ingestion Engines (`app/backend/ingestion/`)

| Path | Primary Responsibility | Key Functions / Classes | Collaborators / Callers |
| :--- | :--- | :--- | :--- |
| `anime/fetch_all.py` | Bulk AniList GraphQL ingestion with adult content guards | `fetch_all_anime()`, `process_anime_node()` | Standalone / Ingestion CLI |
| `anime/fetch_animes.py` | Targeted anime title query and ingestion | `fetch_and_save()` | Ingestion scripts |
| `anime/fetch_manga.py` | AniList manga series ingestion with Hentai genre exclusion | `fetch_and_save()` | Ingestion scripts |
| `tmdb_client.py` | Resilient TMDb HTTP client with retry logic and adult filtering | `_get()`, `get_movie_details()`, `get_tv_details()` | TMDb Sync services |
| `news/` sources | Specialized RSS scrapers (ANN, Crunchyroll, SlashFilm, ComicBook) | `fetch_ann_news()`, `fetch_crunchyroll_news()` | `news_pipeline_service.py` |

---

## 4. Technology & Model Inventory

| Technology / Component | Version / Specification | Role in System | Architectural Rationale |
| :--- | :--- | :--- | :--- |
| **FastAPI** | `>=0.115.0` | Primary Web API Framework | High-throughput asynchronous concurrency (`asyncio`), native Pydantic validation, OpenAPI specs. |
| **Motor (Async PyMongo)**| `>=3.6.0` | Asynchronous MongoDB Driver | Non-blocking database I/O preventing event-loop stalls during heavy aggregate queries. |
| **Google Gemini 2.5 Flash** | `gemini-2.5-flash` | Primary LLM (Agent & Chat) | Sub-second latency, massive context window (1M tokens), strong structured tool-calling performance. |
| **Google GenAI SDK** | `>=1.0.0,<3.0.0` | Official Google AI Client | Standardized API client for Gemini with native tool declarations and streaming support. |
| **Sentence-Transformers** | `all-MiniLM-L6-v2` | Dense Lore Embedding Model | Local inference (no external API cost/rate-limits), fast CPU execution, 384-dimension high-quality semantic vectors. |
| **MongoDB Atlas Vector Search** | Dimension: `384`, Metric: `cosine` | Dense Vector Index (`lore_vector_index`) | Eliminates external vector DB (Pinecone/Milvus); stores vectors colocated with document metadata. |
| **APScheduler** | `3.10.x` | In-Process Task Scheduler | Lightweight periodic execution for news ingestion (every 30m) and daily TMDb discovery without Redis. |
| **Trafilatura** | `2.0.x` | Web Article Text Extraction | Clean HTML-to-text extraction from news RSS links, stripping boilerplate, ads, and navigation chrome. |
| **PyPDF** | `5.0.x` | Lore PDF Document Parser | Pure Python extraction of structured lore bibles, character guides, and world-building notes. |
| **Cloudinary SDK** | `1.41.x` | Cloud Asset CDN & Storage | Offloads static image uploads (user avatars, custom tierlist covers) from backend storage. |

---

## 5. Data Model & Key Collections

All documents adhere to a strict, prefixed primary key naming standard:

| Collection Name | Prefix Standard | Purpose | Key Indexed Fields |
| :--- | :--- | :--- | :--- |
| `anime` | `anime_<slug>` | AniList anime TV, movies, OVAs | `_id`, `slug`, `genres`, `status`, `averageScore`, `source_metadata.anilist_id` |
| `manga` | `manga_<slug>` | Manga, light novels, one-shots | `_id`, `slug`, `genres`, `status`, `source_metadata.anilist_id` |
| `characters` | `char_<slug>` | Character profiles across anime & manga | `_id`, `name.full`, `anime_ids`, `manga_ids`, `source_metadata.anilist_id` |
| `voice_actors` | `va_<slug>` | Japanese & English voice actors | `_id`, `name.full`, `character_ids`, `source_metadata.anilist_id` |
| `movies` | `movie_<tmdb_id>`| TMDb live-action & animated films | `_id`, `tmdb_id`, `title`, `release_date`, `cast.actor_id` |
| `tv_series` | `tv_<tmdb_id>` | TMDb television series | `_id`, `tmdb_id`, `name`, `first_air_date`, `seasons` |
| `actors` | `actor_<tmdb_id>`| TMDb live-action cast & crew | `_id`, `tmdb_id`, `name`, `known_for_department` |
| `lore_chunks` | Auto ObjectID / hash | Chunked lore texts for vector search | `_id`, `franchise_id`, `canon_tier`, `embedding` (384-dim), `chunk_text` |
| `relationships` | `rel_<source>_<target>`| Character relations (family, rival, ally)| `_id`, `character_1_id`, `character_2_id`, `relationship_type` |
| `news` | Auto hash / slug | Syndicated media news articles | `_id`, `url` (unique), `published_at`, `categories`, `title` |
| `users` | Auto ObjectID | User accounts & permissions | `_id`, `email` (unique), `role` (`user` / `admin`), `password_hash` |

---

## 6. Critical Workflows Deep-Dive

### Flow A: Lore PDF Ingestion to Vector RAG
```
[User PDF Upload] 
       │
       ▼
1. Extract text page-by-page via `pypdf`
       │
       ▼
2. Normalize markdown headings & whitespace (`normalize_markdown_spacing`)
       │
       ▼
3. Chunk into semantic passages (~500 tokens, 100 overlap)
       │
       ▼
4. Generate 384-dim embeddings via `all-MiniLM-L6-v2` (Local PyTorch)
       │
       ▼
5. Insert documents into `lore_chunks` collection
       │
       ▼
6. Atlas `$vectorSearch` indexes vector using HNSW index `lore_vector_index`
```

### Flow B: Autonomous Tool-Calling Agent (`POST /agent`)
```
[User Message] ──> [FastAPI Route] ──> [Agent Service]
                                             │
                                             ▼
                                 [Gemini Model Invocation]
                                 (Sends query + 7 Tool Schemas)
                                             │
                         ┌───────────────────┴───────────────────┐
                         ▼                                       ▼
                  [Direct Response]                     [Function Call Request]
                         │                                       │
                         │                                       ▼
                         │                             [Execute Local Async Tool]
                         │                             - search_anime_database
                         │                             - search_character_database
                         │                             - search_relationships
                         │                             - search_lore
                         │                             - search_media_news
                         │                             - find_voice_actor
                         │                             - get_top_trending
                         │                                       │
                         │                                       ▼
                         │                             [Feed Tool Result Back]
                         │                                       │
                         │                                       ▼
                         │                             [Gemini Final Synthesis]
                         │                                       │
                         └───────────────────┬───────────────────┘
                                             ▼
                                  [JSON Response to User]
```

---

## 7. Architectural Decisions & Tradeoffs

1. **Local MiniLM Embedding vs. Remote Cloud Embeddings (e.g. OpenAI / Google)**
   - *Decision*: Embed lore locally using `all-MiniLM-L6-v2`.
   - *Rationale*: Eliminates network latency, zero per-token embedding costs, immune to third-party rate limits, perfectly reproducible 384-dim dense vectors.
   - *Tradeoff*: Requires local PyTorch runtime dependencies (~100MB download on cold start).

2. **MongoDB Atlas Vector Search vs. Dedicated Vector DB (Pinecone/Milvus)**
   - *Decision*: Colocate vector index inside MongoDB Atlas.
   - *Rationale*: Single source of truth. Allows pre-filtering and post-filtering against relational metadata (`franchise_id`, `canon_tier`) without syncing data across two disparate databases.
   - *Tradeoff*: Vector index changes in Atlas are asynchronous; indexing has a brief eventual consistency delay.

3. **In-Memory APScheduler vs. Celery + Redis**
   - *Decision*: Run periodic ingestion tasks inside FastAPI via `APScheduler`.
   - *Rationale*: Dramatically reduced operational footprint—no need to run, configure, and monitor Redis brokers or Celery workers for a single-server deployment.
   - *Tradeoff*: Long-running CPU-bound tasks must yield to the event loop, and tasks do not persist across server restarts.

4. **Multi-Tool Autonomous Agent vs. Plain Context Stuffing**
   - *Decision*: Provide Gemini with 7 discrete repository query tools.
   - *Rationale*: Prevents prompt blowup and hallucination. The LLM only receives exact database documents that match its active reasoning step.

---

## 8. Real-World Bug Log & Production Solutions

### 1. MongoDB Atlas Vector Search Sync Lag
- **Issue**: During automated tests, creating a lore chunk and immediately querying it via `$vectorSearch` returned 0 results.
- **Root Cause**: Atlas Vector Search uses Lucene-based eventual consistency; documents are indexed asynchronously outside the main BSON write concern.
- **Solution**: Implemented an exponential backoff polling retry loop in integration tests (`scripts/test_lore_pipeline.py`) that waits up to 10 seconds for the Atlas vector index to catch up before asserting query matches.

### 2. PDF Header Gluing & Markdown Chunk Fragmentation
- **Issue**: Extracted PDF lore text frequently merged section headers into preceding paragraphs, causing the chunker to miss semantic boundaries.
- **Root Cause**: `pypdf` extracts raw text streams where newlines between distinct visual boxes are stripped.
- **Solution**: Created `normalize_markdown_spacing()`, a regex-based pre-processor that identifies heading patterns (`#`, `##`, all-caps lines) and injects standardized newline delimiters prior to chunking.

### 3. Entity Name Collisions Across Unrelated Franchises
- **Issue**: Common character names (e.g., "Kohaku" in *Dr. STONE* vs *InuYasha*) caused records to accidentally overwrite each other when keyed purely on name slug.
- **Root Cause**: Slug generation was initially derived solely from `character_name`.
- **Solution**: Refactored character resolution (`resolve_or_create_character`) to prioritize `source_metadata.anilist_id` as the primary deduplication anchor, preserving unique IDs for distinct characters sharing identical display names.

### 4. News Ingestion Rate-Limiting & Bot Blocking
- **Issue**: Certain RSS feeds (e.g. SlashFilm, ScreenRant) returned 403 Forbidden during automated scraping.
- **Root Cause**: Default HTTP client headers triggered Cloudflare anti-bot rules.
- **Solution**: Configured realistic browser `User-Agent` headers and relaxed connection timeouts with backoff retries in `app/backend/ingestion/news/sources/`.

---

## 9. Known Limitations & Technical Debt

1. **In-Process Task Scheduling**: `APScheduler` runs within the FastAPI Uvicorn process. If multiple Uvicorn worker processes are launched (`workers > 1`), jobs would run redundantly. For multi-worker deployments, jobs must be decoupled into Celery or a distributed cron runner.
2. **Local Model Cold Start**: The first invocation of `embedding_service.py` downloads and caches `all-MiniLM-L6-v2` weights into memory (~90MB). On constrained serverless platforms, this can cause a 3–5 second cold-start penalty.
3. **Synchronous Image Processing**: Some image operations rely on direct URL passing rather than streaming background transformations.

---

## 10. Local Setup & Execution Guide

### 1. Environment Configuration
Ensure `.env` contains:
```env
MONGO_URI=mongodb+srv://<user>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority
MONGO_DB_NAME=anime_ai
GEMINI_API_KEY=AIzaSy...
TMDB_API_KEY=...
JWT_SECRET_KEY=super-secret-key-32-chars-minimum
```

### 2. Starting the Backend Server
```bash
# In the anime_ai directory:
python -m uvicorn app.main:app --reload --port 8000
```

### 3. Running Test Suites
```bash
# Run unit & integration tests
pytest tests/ -v
```

### 4. Seed Data & Index Setup
```bash
# Ensure indexes and initial seed collections are created:
python -m app.scripts.create_search_indexes
python -m app.scripts.seed_data
```

---

## 11. Technical Interview Defense: Anticipated Questions & Live Code Changes

### Question 1: "Why use MongoDB instead of PostgreSQL + pgvector for this architecture?"
> **Answer**: "The domain model features heterogeneous entities (anime, manga, movies, live actors, voice actors) where field schemas diverge significantly—TMDb has season/episode production crews; AniList has Japanese romaji/native titles, studios, and air seasons. MongoDB's polymorphic document model accommodates these schema variations natively without requiring complex relational joins across 15 nullable tables. Furthermore, MongoDB Atlas Vector Search colocates vector embeddings with full-text search and document fields, enabling efficient compound filtering in a single `$vectorSearch` pipeline."

### Question 2: "How do you prevent the autonomous agent from hallucinating or running into infinite tool-calling loops?"
> **Answer**: "We constrain the agent execution loop in `agent_service.py` with two explicit guardrails:
> 1. A maximum iteration cap (`MAX_ITERATIONS = 5`), breaking immediately if the model exceeds this depth.
> 2. Strict tool schemas with parameter validation. If an empty or irrelevant result is returned by a tool, the model is prompted with a system fallback directing it to state that information was not found rather than inventing facts."

### Question 3: "How does the platform handle adult/NSFW content during ingestion?"
> **Answer**: "Adult filtering is enforced at the network ingestion boundary rather than post-storage:
> 1. **Anime & Manga (AniList)**: We specify `isAdult: false` directly in the GraphQL query parameters. At the ingestion parser level (`fetch_all.py`, `fetch_animes.py`, `fetch_manga.py`), we inspect the `genres` array and reject any item containing `"Hentai"`.
> 2. **Movies & TV Series (TMDb)**: 
>    - At the API client boundary (`tmdb_client.py`), we inject `include_adult="false"` into every outbound HTTP request parameter.
>    - At the synchronization and discovery layers (`tmdb_sync_service.py` and `daily_discovery_service.py`), we explicitly verify `if details.get("adult") is True:` and skip processing adult movies or TV series.
>    - In `tmdb_mapper.py`, we map `"is_adult": details.get("adult", False)`, and the repository queries (`home_repository.py`) filter with `{"is_adult": {"$ne": True}}` to prevent adult media from surfacing.
> 3. **Actors & Cast**: `ingest_tmdb_actors.py` checks `if person_data.get("adult"):` to exclude adult performers from being ingested."

---

### Live Coding Scenarios: Quick Reference for 5-Minute Changes

#### Scenario A: "Add a new tool to the `/agent` endpoint (e.g., search movies by year)."
- **Files to touch**: `app/services/agent_service.py`
- **Steps**:
  1. Define the tool function `search_movies_by_year(year: int)` querying `movie_repository`.
  2. Add the tool declaration schema in `TOOL_DECLARATIONS` with parameter specifications.
  3. Add the mapping in the agent dispatch dictionary: `"search_movies_by_year": search_movies_by_year`.

#### Scenario B: "Change the Lore chunk size or overlap for RAG retrieval."
- **Files to touch**: `app/services/lore_service.py`
- **Steps**:
  1. Locate `CHUNK_SIZE` and `CHUNK_OVERLAP` constants at the top of the file.
  2. Adjust `CHUNK_SIZE = 750` and `CHUNK_OVERLAP = 150`.
  3. Re-ingest the document using `POST /lore/upload`.

#### Scenario C: "Add an extra rate limiter or endpoint to health checks."
- **Files to touch**: `app/api/routes/health.py`
- **Steps**:
  1. Add new router method `@router.get("/ping")`.
  2. Return `{"status": "pong", "timestamp": datetime.utcnow()}`.

---

## 12. Two-Minute Live Demo Script

1. **System Health & Connectivity**:
   - Call `GET http://localhost:8000/health`.
   - *Demonstrates*: MongoDB connection is active, collections are loaded (4,800+ anime, 53,000+ characters).
2. **Autonomous Agent Execution**:
   - Open frontend or Postman: `POST http://localhost:8000/agent` with payload:
     ```json
     {"message": "Who voices Gojo Satoru, and what other anime are they famous for?"}
     ```
   - *Demonstrates*: Tool calling in action—Gemini invokes `search_character_database`, resolves Yuichi Nakamura, and synthesizes his voice acting career.
3. **Lore Document RAG**:
   - Query `POST http://localhost:8000/lore/query` with an uploaded franchise lore question:
     ```json
     {"query": "What are the rules of the Six Eyes technique in Jujutsu Kaisen?", "franchise_id": "anime_jujutsu_kaisen"}
     ```
   - *Demonstrates*: Local dense vector retrieval (`all-MiniLM-L6-v2`) finding exact context chunks and answering with grounded source citations.
4. **Live Ingestion Feed**:
   - Call `GET http://localhost:8000/news/latest?limit=5`.
   - *Demonstrates*: Automated background RSS pipeline syncing real-time articles with categories and publisher attribution.
