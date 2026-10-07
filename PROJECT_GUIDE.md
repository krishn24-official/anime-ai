# AnimeAI (AniVerse): Technical Architecture & Defense Guide

---

## 1. Executive Summary & Project Purpose

**AnimeAI** (AniVerse) is an asynchronous entertainment platform that unifies entertainment records—spanning anime series, manga volumes, movies, television series, voice actors, character relationships, fictional organizations, real-time syndicated entertainment news, and narrative world lore—into a consolidated document store and conversational AI engine.

The backend is built with **FastAPI** (Python 3.11+) and backed by a **MongoDB Atlas** cluster combining polymorphic document collections with dense vector search. The system implements:
1. **Autonomous Tool-Calling Agent (`/agent`)**: A multi-turn reasoning agent powered by Google Gemini (`gemini-2.5-flash`) with 9 registered database tools and automated intent dispatch.
2. **Conversational Assistant (`/chat`)**: A conversational engine featuring multimodal image recognition, intent keyword resolution (e.g., family/mentor/rival relationships), and grounded RAG over deep series lore.
3. **PDF Lore Ingestion & RAG Pipeline (`/admin/lore`)**: In-memory PDF parsing via `pypdf`, structural markdown header normalization, semantic chunking with sibling merge guards, local 384-dimensional vector embedding via `SentenceTransformer("all-MiniLM-L6-v2")`, and vector retrieval via MongoDB Atlas Vector Search.
4. **Tri-Pillar Trending Engine (`/content/trending`)**: Real-time ranking driven by user search spike logs, automated RSS news entity mentions, and admin-pinned Editor's Picks.
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
|  [ 24 Mounted Routers (app/api/router.py) + 3 Root Endpoints (/ws, /, /health in app/main.py) ]:         |
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
| 29 Modules)  |  +----------------+  +------------------+  +---------------+  +------------------+
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

---

## 3. Technology & Model Inventory

### Model and Tool Inventory Table

| Purpose | Exact Model String | File / Function | Local vs API | Cost / Limits | Fallback Chain |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Conversational Assistant & Lore RAG** | `GEMINI_MODEL_NAME` (Default: `"gemini-2.5-flash"`) | `app/services/gemini_service.py` : `_generate_with_fallback` | Remote Google GenAI API | `DAILY_LIMIT` = 180 calls/day (in-memory counter) | `[GEMINI_MODEL_NAME, "gemini-2.5-flash-lite", "gemini-3.6-flash"]` |
| **Multimodal Vision (Image Identification)** | `GEMINI_MODEL_NAME` (Default: `"gemini-2.5-flash"`) | `app/services/gemini_service.py` : `identify_image` | Remote Google GenAI API | Consumes from chat `DAILY_LIMIT` (180/day) | None (catches exception, returns `None`) |
| **News Article Categorization & Summary** | `GEMINI_MODEL_NAME` (Default: `"gemini-2.5-flash"`) | `app/services/gemini_service.py` : `categorize_and_summarize_news` | Remote Google GenAI API | `NEWS_DAILY_LIMIT` = 180 calls/day (separate in-memory counter) | None (caller defaults to `category="Other"`, `summary=description`) |
| **News Listicle Article Body Generation** | `GEMINI_MODEL_NAME` (Default: `"gemini-2.5-flash"`) | `app/services/gemini_service.py` : `generate_listicle_article_body` | Remote Google GenAI API | Consumes from `NEWS_DAILY_LIMIT` (180/day) | None (returns `""`) |
| **Autonomous AI Agent Execution** | `GEMINI_MODEL_NAME` (Default: `"gemini-2.5-flash"`) | `app/services/agent_service.py` : `run_agent` | Remote Google GenAI API | API quota, capped at `MAX_ITERATIONS = 5` | None (catches exception, returns `"Agent error: ..."`) |
| **Game Property Extractor** | `GEMINI_MODEL_NAME` (Default: `"gemini-2.5-flash"`) | `app/services/game_property_extractor.py` : `extract_game_properties` | Remote Google GenAI API | Standard API quota | None (returns `{}`) |
| **Dense Lore Vector Embedding** | `LORE_EMBEDDING_MODEL` (Default: `"all-MiniLM-L6-v2"`) | `app/services/lore_service.py` : `LoreEmbedder` | Local PyTorch (`SentenceTransformer`) | Free local CPU execution, 384 dimensions | Tries `local_files_only=True`, then downloads from HuggingFace cache |

> [!NOTE]
> **Configuration vs Documentation Discrepancy**:
> - `app/config.py` sets `GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")`.
> - `.env.example` does not declare `GEMINI_MODEL_NAME`, so environments defaulting to `.env.example` run `gemini-2.5-flash`.
> - `README.md` documents `gemini-2.5-flash-lite`. Both are valid models in Google AI Studio, and `gemini-2.5-flash-lite` serves as the second tier in the `_generate_with_fallback` chain.

---

## 4. Lore Ingestion & Markdown Normalization Regexes

In `app/services/lore_service.py`, `normalize_markdown_spacing(text: str)` performs four exact regex transformations to repair artifacts introduced during `pypdf` text stream extraction:

```python
# 1. Heading ungluing: inserts a newline before 1-4 heading hashes followed by a single whitespace,
#    unless already preceded by a newline or another hash (avoids splitting ### mid-run).
text = re.sub(r"(?<![\n#])(#{1,4}\s)", r"\n\1", text)

# 2. Horizontal rule ungluing: inserts a newline before triple hyphens unless preceded by a newline.
text = re.sub(r"(?<!\n)(---)", r"\n\1", text)

# 3. Bullet dash ungluing: inserts a newline before a dash stuck to sentence punctuation or characters,
#    only when followed by whitespace and an uppercase letter or number.
text = re.sub(r"(?<=[a-zA-Z0-9.,;:])-(?=\s+[A-Z0-9])", r"\n-", text)

# 4. Whitespace compaction: collapses runs of three or more newlines down to double newlines.
text = re.sub(r"\n{3,}", "\n\n", text)
```

### Chunking Pipeline Details
1. **Markdown Detection**: `looks_like_markdown()` checks for at least 2 occurrences of `^#{1,4}\s+.+$` across multiline text.
2. **Breadcrumb Tracking**: Sections are parsed into a hierarchy where breadcrumbs (e.g., `Titan Origins > The Nine Titans > The Attack Titan`) are computed and prefixed to each chunk text.
3. **Safe Sibling Merging**: `_is_safe_merge_target(curr, next)` ensures undersized sections (< 200 characters) only merge into direct siblings sharing the same heading level and parent title.
4. **Fallback Splitting**: Non-markdown text or oversized sections split recursively using separators `["\n\n", "\n", ". ", " ", ""]` within `LORE_CHUNK_SIZE=800` and `LORE_CHUNK_OVERLAP=100`.

---

## 5. Data Model & Primary Key Standards

### Primary Key (`_id`) Formats and Collection Specs

| Collection Name | Primary Key (`_id`) Format | Example `_id` | Full Field List / Key Schema |
| :--- | :--- | :--- | :--- |
| `lore_chunks` | UUID string (`chunk.chunk_id`) | `550e8400-e29b-41d4-a716-446655440000` | `_id`, `chunk_id`, `series_id`, `character_ids`, `chunk_text`, `embedding_vector` (384-dim), `source_file`, `section_title`, `created_at` |
| `movies` | Slug-based string: `movie_{slug}` | `movie_avengers_endgame`, `movie_inception` | `_id`, `title`, `original_title`, `year`, `release_date`, `runtime_minutes`, `genres`, `director`, `writers`, `cast`, `plot`, `language`, `country`, `rating`, `images`, `trailers`, `status`, `tagline`, `budget`, `revenue`, `content_type`, `source_metadata` (`tmdb_id`, `imdb_id`), `is_adult`, `is_deleted`, `deleted_at` |
| `tv_series` | Slug-based string: `tv_{slug}` | `tv_breaking_bad`, `tv_loki` | `_id`, `title`, `original_title`, `year`, `first_air_date`, `last_air_date`, `total_seasons`, `total_episodes`, `episode_runtime_minutes`, `genres`, `creators`, `cast`, `plot`, `language`, `country`, `rating`, `images`, `trailers`, `status`, `tagline`, `content_type`, `source_metadata` (`tmdb_id`), `is_adult`, `is_deleted`, `deleted_at` |
| `actors` | Slug-based string: `actor_{slug}` (with counter on collision) | `actor_robert_downey_jr`, `actor_chris_evans` | `_id`, `tmdb_id`, `name`, `birthdate`, `biography`, `images` (`profile`), `is_deleted`, `deleted_at`, `source_metadata` |
| `anime` | Slug-based string: `anime_{slug}` | `anime_naruto`, `anime_attack_on_titan` | `_id`, `slug`, `title` (`english`, `romaji`, `native`), `synonyms`, `format`, `status`, `genres`, `season`, `seasonYear`, `episodes`, `duration`, `averageScore`, `coverImage`, `bannerImage`, `source_metadata` (`anilist_id`), `is_deleted` |
| `manga` | Slug-based string: `manga_{slug}` | `manga_one_piece`, `manga_berserk` | `_id`, `slug`, `name`, `native_name`, `genres`, `status`, `chapters`, `volumes`, `averageScore`, `source_metadata` (`anilist_id`), `is_deleted` |
| `characters` | Slug-based string: `char_{slug}` | `char_naruto_uzumaki`, `char_levi_ackerman` | `_id`, `name`, `native_name`, `role`, `images`, `anime_ids`, `manga_ids`, `description`, `birth_month`, `birth_day`, `game_properties`, `source_metadata` (`anilist_id`), `is_deleted` |
| `relationships` | Composite: `rel_{src}_{tgt}_{type}` | `rel_naruto_uzumaki_sasuke_uchiha_rival` | `_id`, `source_id`, `target_id`, `relationship`, `rel_type`, `context`, `is_deleted` |
| `trending` | Composite: `{content_type}_{content_id}` | `movie_movie_avengers_endgame` | `content_type`, `content_id`, `source`, `reason`, `score`, `pinned`, `set_by`, `note`, `expires_at`, `custom_poster` |
| `trending_mentions`| Composite: `{content_id}_{news_id}` | `movie_avengers_endgame_660...` | `content_id`, `news_id`, `matched_at` (TTL: 48 hours) |
| `search_logs` | Auto ObjectId | `661234...` | `content_id`, `searched_at` (TTL: 3 hours) |
| `users` | Auto ObjectId | `660abc...` | `_id`, `email`, `username`, `password_hash`, `is_admin`, `created_at` |
| `refresh_tokens` | Auto ObjectId | `660def...` | `_id`, `user_id`, `token`, `expires_at` (TTL index) |

### Slug Function Clarification
- **`app/backend/utils/slug.py:create_slug(text)`**: Generic slug generator for titles and names: `re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")`.
- **`app/services/relationship_admin_service.py:_slug(text)`**: Specialized relationship helper that strips `"char_"` and removes non-alphanumeric characters for clean composite relationship IDs.
- *(Note: There is no `make_slug` in the codebase).*

---

## 6. Directory, Router & Repository Inventory

- **API Routers**: Exactly **24 sub-routers** registered in `app/api/router.py`:
  - `character`, `relationship`, `anime`, `manga`, `health`, `home`, `event`, `search`, `chat`, `news`, `auth`, `movies`, `tv_series`, `content`, `agent`, `game`, `tier_list`, `admin_news`, `organizations`, `admin_content`, `actors`, `admin_actors`, `voice_actors`, `admin_lore`.
  - Plus 3 root endpoints directly on `app` in `app/main.py`: `GET /`, `GET /health`, and `WebSocket /ws`.
  - Exactly 3 routes in `app/api/routes/admin_lore.py`: `POST /upload`, `DELETE /{series_id}`, `GET /{series_id}/status`.
- **Repositories**: Exactly **29 repository modules** in `app/repositories/`:
  - `actors_repository.py`, `anime_repository.py`, `chapter_repository.py`, `character_admin_repository.py`, `character_repository.py`, `chat_repository.py`, `comment_repository.py`, `content_repository.py`, `episode_repository.py`, `event_repository.py`, `game_repository.py`, `health_repository.py`, `home_repository.py`, `lore_repository.py`, `manga_repository.py`, `manual_news_repository.py`, `movie_repository.py`, `news_repository.py`, `organization_repository.py`, `rating_repository.py`, `refresh_token_repository.py`, `relationship_repository.py`, `search_repository.py`, `tier_list_repository.py`, `trending_repository.py`, `tv_series_repository.py`, `user_repository.py`, `voice_actors_repository.py`, `watchlist_repository.py`.
- **Utility Directory**: `app/utils/` exists and contains 1 module: `search_utils.py` (`build_fuzzy_search_regex`).

---

## 7. Real-World Bug Log & Production Incidents

### Incident 1: MongoDB Atlas Vector Search Sync Lag
- **Issue**: Automated pipeline integration tests (`scripts/test_lore_pipeline.py`) inserted lore chunks and immediately ran `$vectorSearch`, resulting in 0 retrieved results.
- **Root Cause**: MongoDB Atlas Vector Search employs Lucene-based asynchronous indexing. Vector embedding documents are not queryable via `$vectorSearch` until the background index sync completes.
- **Solution**: Implemented an exponential backoff retry loop in the test runner that polls `$vectorSearch` with a timeout of up to 10 seconds before asserting retrieval success.

### Incident 2: Extracted PDF Glued Headings (`Important Examples#### Eren Kruger`)
- **Issue**: Ingested Attack on Titan lore documents frequently failed to identify section boundaries, causing entire character subsections to merge into one giant block.
- **Root Cause**: `pypdf` extracted text streams where line breaks between visual bounding boxes were omitted, resulting in text strings like `"Important Examples#### Eren Kruger"`. Standard regexes anchored to line starts (`^#{1,4}\s+`) failed to detect the heading.
- **Solution**: Created `normalize_markdown_spacing()` in `lore_service.py` using negative lookbehinds: `re.sub(r"(?<![\n#])(#{1,4}\s)", r"\n\1", text)`.

### Incident 3: Markdown Section Merging Bridging Unrelated Narrative Arcs
- **Issue**: Short character entries (< 200 chars) were merging forward into subsequent sections that belonged to completely different chapters or narrative arcs.
- **Root Cause**: The original merge logic combined adjacent undersized sections without checking heading depth or parent section boundaries.
- **Solution**: Implemented `_is_safe_merge_target(curr, next)` in `lore_service.py:180-205`, enforcing that a merge target must share the exact same heading level, parent title, and breadcrumb path.

### Incident 4: `series_id` Mismatch in Agent and User Lore Queries
- **Issue**: When the agent called `query_lore(query="...", series_id="Attack on Titan")`, Atlas `$vectorSearch` returned 0 results because chunks were stored under `anime_attack_on_titan`.
- **Root Cause**: The LLM agent passed human titles, but `lore_chunks` were indexed with collection-prefixed IDs.
- **Solution**: Developed `resolve_series_id()` in `lore_service.py:569-724`, which checks prefixed IDs, strips prefixes to slugify, queries database title indexes, and resolves canonical IDs before issuing vector queries.

### Incident 5: "on" -> "son" Fuzzy Intent Match Hijacking Series Queries
- **Issue**: Natural language queries like `"Tell me about Attack on Titan"` were being hijacked into relationship queries searching for character sons.
- **Root Cause**: In `chat_service.py`, `difflib.get_close_matches` with a loose threshold matched the short preposition `"on"` to the relationship keyword `"son"`.
- **Solution**: Added `_STOP_WORDS` filtering and an explicit minimum length check (`len(word) >= 4`) in `fuzzy_match_intent()` (`chat_service.py:123-135`).

### Incident 6: One-Word "Titan" Character Hijack
- **Issue**: Searches for multi-word franchise queries like `"Attack on Titan"` or `"Clash of the Titans"` were matching a single character in the database named `"Titan"`, bypassing media results.
- **Root Cause**: Token match scoring rewarded single-token exact word hits over multi-word titles.
- **Solution**: Added a multi-word candidate guard in `chat_service.py:764`: when a query has 2 or more tokens and a candidate has only 1 token, the match is rejected unless the similarity ratio exceeds 0.75.

### Incident 7: Grounding Leak (Positive and Negative Testing)
- **Issue**: When users asked lore questions that contained unmentioned events or non-lore questions (e.g. "What should I watch after Attack on Titan?"), Gemini would invent answers or use general pre-trained knowledge.
- **Root Cause**: Default system prompts did not strictly penalize out-of-context extrapolation.
- **Solution**: Defined `LORE_SYSTEM_PROMPT` in `gemini_service.py:120-136`. Validated via:
  - **Positive Grounding**: Asking about Titan inheritance correctly explains the 13-year curse from the lore document.
  - **Negative Grounding**: Asking "What should I watch after Attack on Titan?" explicitly responds that the lore documents do not contain watch recommendations.

---

## 8. Known Limitations & Technical Debt

1. **Unauthenticated Public AI Endpoints**:
   - `/chat` and `/agent` are public endpoints with no user-level or IP-level rate limiting. Any client can submit queries until the daily Gemini quota is exhausted.
2. **In-Memory Rate Limiting State**:
   - `_usage` and `_news_usage` counters in `gemini_service.py` reside in memory within a single process. They reset on server restart and are not shared across multiple Uvicorn worker processes or cluster nodes.
3. **MongoDB Atlas Vector Search Free-Tier Index Cap**:
   - `lore_vector_index` must be configured manually in MongoDB Atlas. On MongoDB Atlas M0 free clusters, there is a hard cap of **3 search/vector indexes** across the entire cluster.
4. **In-Process Task Scheduling**:
   - `APScheduler` runs inside the FastAPI process. Running Uvicorn with multiple workers (`--workers 4`) causes duplicate task executions.
5. **Local PyTorch Cold Start**:
   - Cold startup requires downloading and loading `SentenceTransformer("all-MiniLM-L6-v2")` (~90MB model weights), incurring a cold-start initialization delay.

---

## 9. Technical Interview Defense: 18 Code-Referenced Questions

1. **How is MongoDB connection management handled across the FastAPI application lifecycle?**
   - *Reference*: `app/main.py:startup`, `app/main.py:shutdown`, `app/db/mongo.py:connect_db`.
   - *Answer*: `connect_db()` initializes an asynchronous `AsyncIOMotorClient` on startup and caches the client reference in `mongo_module.client`. `close_db()` gracefully closes the client during shutdown events.

2. **Why use MongoDB document collections rather than a traditional relational schema?**
   - *Reference*: `app/repositories/*`, `app/backend/ingestion/tmdb_mapper.py`.
   - *Answer*: The data model spans divergent entertainment entities: AniList anime have Japanese title variants and seasonal airing slots; TMDb movies have crew departments, budgets, and release certifications; news articles have unstructured markdown bodies. MongoDB accommodates these schema variations natively without nullable cross-table joins.

3. **How does the codebase prevent default dev credentials from deploying to production?**
   - *Reference*: `app/config.py:27-31`.
   - *Answer*: On startup, `app/config.py` evaluates `if os.getenv("ENVIRONMENT") == "production" or os.getenv("RENDER"):`. If `JWT_SECRET_KEY` is missing or equal to `"dev-secret-change-me"`, it raises `RuntimeError`, halting server boot.

4. **How do test suites avoid corrupting or dropping the production database?**
   - *Reference*: `tests/conftest.py:db_setup`.
   - *Answer*: `conftest.py` sets `os.environ["MONGO_DB_NAME"] = "anime_ai_test"` and asserts `if db.name != "anime_ai_test" and "test" not in db.name: raise RuntimeError(...)`, refusing to run against non-test databases.

5. **How does in-memory Gemini rate limiting work, and what is its operational limitation?**
   - *Reference*: `app/services/gemini_service.py:_can_call_gemini`.
   - *Answer*: Uses a thread-safe `threading.Lock()` protecting daily counters (`_usage["count"]`). It resets when the calendar day changes. The limitation is that state is lost on server reload and is not shared across multi-process workers.

6. **What fallback mechanism exists if the primary Gemini model encounters errors?**
   - *Reference*: `app/services/gemini_service.py:_generate_with_fallback`.
   - *Answer*: In `gemini_service.py`, `_generate_with_fallback` iterates over `[GEMINI_MODEL_NAME, "gemini-2.5-flash-lite", "gemini-3.6-flash"]` sequentially catching exceptions before failing. (Note: `agent_service.py` currently calls `GEMINI_MODEL_NAME` directly).

7. **How does multimodal image recognition work in the chat assistant?**
   - *Reference*: `app/services/gemini_service.py:identify_image`, `app/api/routes/chat.py`.
   - *Answer*: Base64 image strings received in `ChatRequest` are decoded into binary bytes and converted into `types.Part.from_bytes(data=image_bytes, mime_type=...)`, which are passed alongside the prompt to Gemini.

8. **How does `normalize_markdown_spacing` repair PDF stream extraction artifacts?**
   - *Reference*: `app/services/lore_service.py:normalize_markdown_spacing`.
   - *Answer*: Applies negative lookbehinds `(?<![\n#])(#{1,4}\s)` to unglue headings like `"Examples#### Title"`, `(?<!\n)(---)` to unglue horizontal rules, and `(?<=[a-zA-Z0-9.,;:])-(?=\s+[A-Z0-9])` to unglue bullet dashes.

9. **How does hierarchical breadcrumb chunking preserve semantic context?**
   - *Reference*: `app/services/lore_service.py:chunk_markdown_text`, `app/services/lore_service.py:_attach_breadcrumbs`.
   - *Answer*: Builds an ancestor tree from heading depths (H1-H4). Before embedding, each chunk has its breadcrumb path prepended (e.g. `Titans > Nine Titans > Attack Titan\n\n[chunk text]`), allowing dense vector retrieval to match even when the chunk text itself lacks the series name.

10. **How does the system prevent hallucination on narrative lore queries?**
    - *Reference*: `app/services/gemini_service.py:LORE_SYSTEM_PROMPT`.
    - *Answer*: `LORE_SYSTEM_PROMPT` enforces strict negative grounding: the model must answer using only the provided context and must explicitly state when an event, death, or detail is not mentioned.

11. **How is the vector search index configured, and why is it not created via PyMongo?**
    - *Reference*: `app/db/indexes.py:150-174`, `app/repositories/lore_repository.py:vector_search`.
    - *Answer*: Standard B-Tree indexes on `series_id` and `character_ids` are created via PyMongo `create_index`. Atlas Vector Search indexes (`lore_vector_index`) require Lucene-based vector definitions configured directly through the Atlas UI or Atlas API.

12. **How does the autonomous agent loop execute tools, and how is recursion prevented?**
    - *Reference*: `app/services/agent_service.py:run_agent`, `app/services/agent_tools.py:execute_tool`.
    - *Answer*: The loop sends tool declarations in `AGENT_TOOLS` to Gemini, inspects returned `function_calls`, executes local async python functions, and feeds results back as `types.Part.from_function_response`. The loop is bounded by `MAX_ITERATIONS = 5`.

13. **How does intent pre-routing optimize agent performance?**
    - *Reference*: `app/services/agent_service.py:INTENT_PATTERNS`.
    - *Answer*: Regex patterns identify standard deterministic queries (birthdays, anniversaries, recent news) prior to model invocation, mapping them directly to tool execution and avoiding unnecessary LLM roundtrips.

14. **How does the Tri-Pillar Trending engine compute real-time scores?**
    - *Reference*: `app/services/trending_service.py`, `app/services/news_scheduler.py`.
    - *Answer*: Scheduled jobs evaluate `search_logs` within 3 hours (threshold >= 15 searches or 2x baseline) and `trending_mentions` within 48 hours scanned from RSS articles. Admins can pin Editor's Picks with score = 1000.0.

15. **How does the RSS title matcher avoid false positives on short words?**
    - *Reference*: `app/services/title_matcher.py`.
    - *Answer*: Builds word-boundary regex patterns from alias caches, excluding stop words and generic tokens so common verbs/nouns do not trigger entity mention records.

16. **How does `resolve_series_id` resolve informal user input into canonical database IDs?**
    - *Reference*: `app/services/lore_service.py:resolve_series_id`.
    - *Answer*: Checks if the input already starts with a prefix (`anime_`, `movie_`, `tv_`, `manga_`). If not, strips prefixes, slugifies the title, checks each media collection for exact matches, and falls back to regex title searches.

17. **How does the chat service distinguish relationship queries from titles?**
    - *Reference*: `app/services/chat_service.py:734-743`.
    - *Answer*: When `detect_intent(message)` matches a key in `TARGET_RELATIONSHIP_INTENTS` (e.g. father, sensei, mentor), `forced_scope` is set to `"character"`. This prevents media titles like "Naruto" from competing with character records.

18. **How does cast reconciliation handle movie and actor deduplication?**
    - *Reference*: `app/services/cast_reconciliation_service.py:resolve_or_create_actor`.
    - *Answer*: Queries `actors` by `tmdb_id`. If absent, checks case-insensitive name regex to backfill legacy records. If creating a new record, generates `actor_{slug}` and increments a collision counter if duplicate slugs exist.

---

## 10. Two-Minute Live Demo Script (Verified Working Commands)

### Step 1: System Health Verification
Verify server connectivity and collection record counts:
```powershell
Invoke-RestMethod -Uri http://localhost:8000/health
```
*Expected Output*:
```json
{
  "status": "ok",
  "anime_count": 4845,
  "character_count": 53003,
  "relationship_count": 1698,
  "manga_count": 4824
}
```

### Step 2: Lore Upload via Swagger
1. Navigate to: `http://localhost:8000/docs#/Admin%20-%20Lore/upload_lore_pdf_admin_lore_upload_post`
2. Authenticate with an Admin Bearer token.
3. Submit `series_id`: `anime_attack_on_titan` and upload a lore PDF file.
4. *Result*: `pypdf` extracts pages, `normalize_markdown_spacing` cleans headers, `all-MiniLM-L6-v2` embeds chunks, and saves records into `lore_chunks`.

### Step 3: Grounded Conversational Assistant
Submit a relationship query to `/chat`:
```powershell
$body = @{ message = "who is naruto's father" } | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:8000/chat -Method Post -Body $body -ContentType "application/json"
```
*Expected Output*:
```json
{
  "answer": "Naruto Uzumaki's father is Minato Namikaze."
}
```

### Step 4: Negative Grounding Demonstration
Ask a question about an unmentioned fact to demonstrate that the model refuses to hallucinate:
```powershell
$body = @{ message = "What should I watch after Attack on Titan?" } | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:8000/chat -Method Post -Body $body -ContentType "application/json"
```
*Expected Output*:
```json
{
  "answer": "The provided lore documents describe details about the Attack Titan, its characteristics, and specific battles within its story, but they do not contain any information or recommendations about what to watch after Attack on Titan."
}
```

### Step 5: Autonomous Agent Tool Execution
Submit a multi-step query to `/agent`:
```powershell
$body = @{ message = "Which characters have birthdays today?" } | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:8000/agent -Method Post -Body $body -ContentType "application/json"
```
*Expected Output*: Gemini calls `get_today_birthdays`, queries the repository, and returns synthesized character birthday results.

### Step 6: Fast Lore Chunking Unit Test Suite
Demonstrate that the PDF normalization and sibling merge guards pass all unit tests:
```powershell
python -m pytest tests/test_lore_chunking_unit.py -s
```
*Expected Output*: `10 passed in 0.06s`.

---

## 11. UNVERIFIED Features & Implementation Gaps

The following features or configurations are present in references or partial code paths but are **UNVERIFIED** or lack complete end-to-end integration:

1. **`gemini-3.6-flash` Fallback Target**:
   - `gemini-3.6-flash` is listed in the `_generate_with_fallback` list in `app/services/gemini_service.py:141`. However, this is an experimental/future model identifier and is unverified on standard Google AI Studio API production tiers.
2. **Multi-Model Fallback in Autonomous Agent**:
   - `app/services/gemini_service.py:_generate_with_fallback` implements a multi-model fallback chain, but `app/services/agent_service.py` calls `client.models.generate_content(model=GEMINI_MODEL_NAME)` directly without a fallback loop. When Gemini experiences capacity errors (e.g. 503 UNAVAILABLE), the agent returns `"Agent error: 503"` rather than attempting a fallback model.
3. **Multi-Worker Rate Limiting Consistency**:
   - `DAILY_LIMIT` and `NEWS_DAILY_LIMIT` in `app/services/gemini_service.py` use local Python `threading.Lock()` and in-memory dictionaries. They reset on application restarts and are unverified for distributed or multi-worker deployments.
4. **Atlas Vector Search M0 Cluster Free-Tier Index Limit**:
   - MongoDB Atlas M0 free clusters enforce a limit of up to 3 Atlas Search / Vector Search indexes. Defining `lore_vector_index` alongside text indexes on multiple collections can hit this limit if not monitored.
5. **Multi-Year TMDb API Rate Limiting**:
   - In `app/services/daily_discovery_service.py`, multi-year upcoming discovery issues rapid batches of requests to TMDb. The free tier rate limit of 40 requests per 10 seconds is handled with simple sleep delays rather than a distributed token bucket.
6. **Cloudinary Missing Credential Fallback**:
   - In `app/services/trending_service.py:set_manual_trending`, custom poster uploads require Cloudinary. If `CLOUDINARY_CLOUD_NAME` is unset, `upload_image_from_bytes` returns `None` without raising an explicit error to the admin.
7. **Unreferenced Search Utility**:
   - `app/utils/search_utils.py` defines `build_fuzzy_search_regex()`, but this utility is currently unreferenced by repository search implementations.
