# 🎌 Anime AI — Backend API & Intelligence Engine

[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-Async%20Motor%20%2F%20PyMongo-47A248.svg?style=flat-square&logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-2.5%20Flash%20Lite-4285F4.svg?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev/)
[![WebSockets](https://img.shields.io/badge/RealTime-WebSockets-orange.svg?style=flat-square)](https://fastapi.tiangolo.com/advanced/websockets/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

A high-performance backend and AI intelligence engine for the **Anime AI** platform. Built with **FastAPI**, **MongoDB**, **Google Gemini**, and **APScheduler**, this system powers multi-format media cataloging (Anime, Manga, Movies, TV Series, Games), dynamic character relationship graphs, autonomous AI agent interactions, automated news ingestion pipelines with real-time WebSocket notifications, and rich admin CMS management.

---

## 🚀 Key Features

### 1. 📚 Multi-Media Catalog Management
- **Anime & Manga**: Detailed tracking of release status, episode/chapter breakdowns, genres, studios, and synopsis.
- **Movies & TV Series**: TMDb and OMDb metadata synchronization, seasons/episodes structure, and release schedules.
- **Games & Organizations**: Game property extraction and studio/organization registries.

### 2. 👥 Deep Character Profiles & Relationship Graphs
- **Character Metadata**: Role, aliases, gender, status, attributes, and image gallery.
- **Dynamic Relationship Graph**: Map connections (allies, rivals, romance, master/student, family) with bidirectional inverse mapping.
- **Cast & Voice Actor Reconciliation**: Link real-world actors and voice actors to characters across different dubs and media adaptations.

### 3. 🤖 AI Chat & Autonomous Agent (Google Gemini)
- **Multi-Turn Contextual Chat**: Conversational AI powered by `gemini-2.5-flash-lite` tailored for anime and pop culture discussions.
- **Tool-Calling Agent**: Autonomous agent capable of calling backend services as structured tools (content discovery, character queries, tier list generation, etc.).

### 4. 📰 Automated News Ingestion & Real-Time Broadcasts
- **Multi-Source Scraping**: Background ingestion from RSS feeds and major entertainment sites (Trafilatura article extraction).
- **Intelligent Pipeline**: Automatic keyword filtering, category classification, and duplicate detection.
- **Live WebSockets (`/ws`)**: Real-time push notifications of incoming articles with offline catch-up support.

### 5. 🌟 Discovery, Trending & Tier Lists
- **Daily Discovery Engine**: "On This Day" historical releases, weekly suggestions, and trending calculations.
- **Interactive Tier Lists**: Create, customize, and retrieve tier lists across characters and series.

### 6. 🔐 Authentication & Security
- **JWT Authentication**: Short-lived access tokens (15m) + long-lived refresh tokens (30d).
- **Password Security**: Strong hashing with `bcrypt`.
- **OTP Verification**: Secure one-time password delivery via Gmail SMTP.

### 7. 🛠️ Comprehensive Admin CMS
- Full management routes for content, characters, relationships, cast enrichment, news moderation, and actor directories.

---

## 🏗️ Architecture & Tech Stack

| Layer | Technology |
|---|---|
| **Framework** | [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) |
| **Language** | Python 3.10+ |
| **Database** | [MongoDB](https://www.mongodb.com/) (Async Motor & PyMongo) |
| **AI / LLM** | [Google GenAI SDK](https://ai.google.dev/) (`google-genai` / Gemini 2.5 Flash Lite) |
| **Media APIs** | [TMDb API](https://developer.themoviedb.org/docs) & [OMDb API](https://www.omdbapi.com/) |
| **Asset Storage** | [Cloudinary](https://cloudinary.com/) |
| **Task Scheduler** | [APScheduler](https://apscheduler.readthedocs.io/) |
| **Scraping / Parsing** | [Trafilatura](https://trafilatura.readthedocs.io/), [Feedparser](https://feedparser.readthedocs.io/), [Requests](https://requests.readthedocs.io/) |
| **Testing** | [pytest](https://pytest.org/) & [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio) |

---

## 📁 Project Structure

```text
anime_ai/
├── app/
│   ├── api/
│   │   ├── deps.py               # Dependency injection (Auth, DB)
│   │   ├── router.py             # Main API router aggregator
│   │   └── routes/               # Modular route endpoints
│   │       ├── actors.py         # Actor / Cast routes
│   │       ├── admin_content.py  # Admin CMS for anime, manga, movies, TV
│   │       ├── admin_news.py     # Admin news management
│   │       ├── agent.py          # AI agent endpoints
│   │       ├── anime.py          # Public anime routes
│   │       ├── auth.py           # Login, register, OTP verification
│   │       ├── character.py      # Character profile routes
│   │       ├── chat.py           # AI chat conversation routes
│   │       ├── content.py        # Unified content endpoints
│   │       ├── manga.py          # Public manga routes
│   │       ├── news.py           # Public news endpoints
│   │       ├── relationship.py   # Character relationship graph
│   │       ├── search.py         # Global search & filters
│   │       ├── tier_list.py      # Tier list creation & retrieval
│   │       └── ...
│   ├── backend/
│   │   ├── ingestion/            # Scraping, TMDb sync, and data pipelines
│   │   └── transformers/         # Data transformation & normalization
│   ├── config.py                 # App configuration & environment settings
│   ├── db/
│   │   ├── mongo.py              # Async MongoDB client & connection lifecycle
│   │   ├── init_db.py            # DB connectivity health checks
│   │   ├── setup_collections.py  # Collection initialization
│   │   └── indexes.py            # Index definitions for search & performance
│   ├── main.py                   # FastAPI app entrypoint, middleware, WebSockets
│   ├── repositories/             # Data access layer for MongoDB collections
│   ├── schemas/                  # Pydantic models for validation and responses
│   └── services/                 # Business logic, AI, scraping, auth & schedulers
├── scripts/                      # Utility scripts (e.g. data updates, migrations)
├── tests/                        # Comprehensive test suite
├── .env.example                  # Environment variables template
├── pytest.ini                    # Pytest configuration
├── requirements.txt              # Project dependencies
└── README.md                     # Project documentation
```

---

## ⚙️ Getting Started

### Prerequisites

- **Python 3.10+**
- **MongoDB** (Local instance or MongoDB Atlas cluster)
- **API Keys**:
  - Google Gemini API Key
  - TMDb API Key (optional for TMDb sync)
  - OMDb API Key (optional for movie metadata)
  - Cloudinary Account (optional for image hosting)
  - Gmail App Password (optional for OTP email service)

---

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/anime_ai.git
   cd anime_ai
   ```

2. **Create and activate a virtual environment**:
   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```

---

## 🏃 Running the Application

Start the development server using **Uvicorn**:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Once running:
- **API Server**: `http://localhost:8000`
- **Interactive OpenAPI Documentation (Swagger UI)**: `http://localhost:8000/docs`
- **Alternative Documentation (ReDoc)**: `http://localhost:8000/redoc`
- **Health Check**: `http://localhost:8000/health`

---

## 🔌 WebSockets

Connect to the real-time news WebSocket feed at:

```text
ws://localhost:8000/ws
```

### Query Parameters:
- `last_checked` *(optional, float/timestamp)*: If provided, the server automatically transmits any news articles published while the client was disconnected (catch-up mode).

### Message Event Format:
```json
{
  "type": "NEW_ARTICLE",
  "data": {
    "id": "65b9...",
    "title": "Solo Leveling Season 2 Release Update",
    "summary": "...",
    "source": "AnimeNewsNetwork",
    "url": "https://...",
    "image_url": "https://...",
    "category": "Anime",
    "published_at": "2026-09-07T12:00:00Z"
  }
}
```

---

## 🧪 Running Tests

The test suite covers authentication, character administration, relationship graphs, news pipelines, trending calculations, and cast reconciliation.

Run all tests with:

```bash
pytest
```

Run with verbose output and test coverage:

```bash
pytest -v
```

---

## 🔐 Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `MONGO_URI` | **Yes** | — | MongoDB connection connection string (e.g. `mongodb://localhost:27017` or Atlas URI) |
| `MONGO_DB_NAME` | No | `anime_ai` | MongoDB database name |
| `GEMINI_API_KEY` | **Yes** | — | Google Gemini API key for AI Chat and Agent tools |
| `TMDB_API_KEY` | Optional | — | The Movie Database (TMDb) API key for metadata syncing |
| `OMDB_API_KEY` | Optional | — | Open Movie Database (OMDb) API key |
| `CLOUDINARY_CLOUD_NAME` | Optional | — | Cloudinary cloud name for image uploads |
| `CLOUDINARY_API_KEY` | Optional | — | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | Optional | — | Cloudinary API secret |
| `JWT_SECRET_KEY` | **Yes** | `dev-secret-...` | Secret key for signing JWT tokens |
| `JWT_EXPIRE_MINUTES` | No | `15` | JWT access token expiration duration (minutes) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | `30` | Refresh token expiration duration (days) |
| `GMAIL_SENDER` | Optional | — | Sender email address for OTP verification emails |
| `GMAIL_APP_PASSWORD` | Optional | — | Gmail 16-character App Password |
| `LORE_CHUNK_SIZE` | No | `800` | Chunk size for RAG lore document chunking |
| `LORE_CHUNK_OVERLAP` | No | `100` | Overlap size between adjacent text chunks |
| `LORE_EMBEDDING_MODEL` | No | `all-MiniLM-L6-v2` | Embedding model for vectorizing lore text |
| `LORE_TOP_K` | No | `5` | Top-K closest documents retrieved in vector search |
| `LORE_VECTOR_INDEX_NAME` | No | `lore_vector_index` | MongoDB Atlas Vector Search index name |


---

## 🤝 Related Projects

- **Frontend Repository**: `anime_ai_FE` (Vite, React, TypeScript, Capacitor / Tauri cross-platform client)

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
