from fastapi import FastAPI
from app.db.mongo import connect_db, close_db
from app.db.init_db import check_db
from app.db.setup_collections import create_collections
from app.db.indexes import create_indexes
from app.api.routes.character import router
from app.api.router import (
    api_router
)

app = FastAPI()


app.include_router(
    api_router
)


@app.on_event("startup")
async def startup():
    await connect_db()
    await check_db()

    # 🔥 create structure
    await create_collections()
    await create_indexes()


@app.on_event("shutdown")
async def shutdown():
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