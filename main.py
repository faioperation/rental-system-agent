from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from routers import chat, dashboard, viewings
from services.rag_service import get_embedder

app = FastAPI(title="Aria — AI Real Estate Lead & Viewing Agent")


@app.on_event("startup")
async def preload_models():
    """
    Load the fastembed embedding model once at server boot instead of on the
    first user request — avoids blocking the event loop (and the very first
    customer) with a ~30-60s model download/load.
    """
    get_embedder()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(chat.router)
app.include_router(dashboard.router)
app.include_router(viewings.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
