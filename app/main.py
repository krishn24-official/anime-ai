from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.db.mongo import connect_db, close_db
from app.db.init_db import check_db
from app.db.setup_collections import create_collections
from app.db.indexes import create_indexes
from app.api.routes.character import router
from app.api.router import (
    api_router
)
from app.services.news_scheduler import start_news_scheduler, stop_news_scheduler
from app.services.websocket_manager import manager
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex="https://.*\\.vercel\\.app",  # Matches any Vercel staging or production subdomains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    api_router
)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, last_checked: float | None = None):
    await manager.connect(websocket)

    # Catch up on any news published while client was offline
    if last_checked:
        try:
            from app.db.mongo import get_db
            from app.services.news_date_utils import normalize_datetime
            from app.services.news_service import _serialize
            
            db = get_db()
            last_checked_dt = normalize_datetime(last_checked)
            if last_checked_dt:
                cursor = db["news"].find({"published_at": {"$gt": last_checked_dt}}).sort("published_at", 1).limit(10)
                async for doc in cursor:
                    await websocket.send_json({
                        "type": "NEW_ARTICLE",
                        "data": _serialize(doc)
                    })
        except Exception as err:
            print("[ws] Error sending catch-up notifications:", err)

    try:
        while True:
            # Maintain connection alive, ignore incoming client messages for now
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


@app.on_event("startup")
async def startup():
    await connect_db()
    await check_db()

    # 🔥 create structure
    await create_collections()
    await create_indexes()

    start_news_scheduler()


@app.on_event("shutdown")
async def shutdown():
    stop_news_scheduler()
    await close_db()


@app.get("/")
async def root():
    return {"status": "Anime AI DB running 🚀"}


@app.get("/health")
async def health():
    ok = await check_db()
    return {"db": "connected" if ok else "failed"}

@app.get("/debug-db")
async def debug_db():
    from app.db.mongo import get_db
    db = get_db()

    collections = await db.list_collection_names()

    return {
        "db_name": db.name,
        "collections": collections
    }