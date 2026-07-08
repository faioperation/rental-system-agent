import asyncio
import csv
import io
from fastapi import APIRouter, Request, Query, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from services import ticket_service, rag_service, memory_service

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="templates")


# ---------- Customer-facing chat page ----------
@router.get("/", response_class=HTMLResponse)
async def chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})


# ---------- Internal admin dashboard (Leads / Properties / Viewings) ----------
@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})


@router.get("/api/tickets")
async def get_tickets(status: str | None = Query(default=None), priority: str | None = Query(default=None)):
    return ticket_service.list_tickets(status=status, priority=priority)


@router.get("/api/conversations/{conversation_id}/history")
async def get_history(conversation_id: str):
    history = memory_service.get_recent_history(conversation_id, limit=50)
    return history


class PropertyIn(BaseModel):
    title: str
    listing_type: str = "rent"          # 'rent' | 'sale'
    address: str = ""
    city: str = ""
    neighborhood: str = ""
    price: float | None = None
    bedrooms: int | None = None
    bathrooms: float | None = None
    sqft: int | None = None
    features: list[str] = []
    description: str = ""


@router.post("/api/properties")
async def add_property(prop: PropertyIn):
    inserted = await asyncio.to_thread(rag_service.add_property, prop.model_dump())
    return {"status": "ok", "property": inserted}


@router.get("/api/properties")
async def list_properties():
    from database.supabase_client import get_supabase

    supabase = get_supabase()
    result = (
        supabase.table("properties")
        .select("id, title, listing_type, city, neighborhood, price, bedrooms, bathrooms, status")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


@router.post("/api/properties/bulk-csv")
async def bulk_import_properties(file: UploadFile = File(...)):
    """
    Bulk-import listings from a CSV export (e.g. from the client's existing
    spreadsheet or CRM). Expected columns (header row required):
    title, listing_type, address, city, neighborhood, price, bedrooms,
    bathrooms, sqft, features, description
    `features` should be a semicolon-separated list, e.g. "parking;pet_friendly".
    Any missing optional column is fine — it'll just be left blank/null.
    """
    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))

    inserted, failed = 0, []
    for i, row in enumerate(reader, start=2):  # row 1 is the header
        try:
            prop = {
                "title": row.get("title", "").strip(),
                "listing_type": (row.get("listing_type") or "rent").strip().lower(),
                "address": (row.get("address") or "").strip(),
                "city": (row.get("city") or "").strip(),
                "neighborhood": (row.get("neighborhood") or "").strip(),
                "price": float(row["price"]) if row.get("price") else None,
                "bedrooms": int(row["bedrooms"]) if row.get("bedrooms") else None,
                "bathrooms": float(row["bathrooms"]) if row.get("bathrooms") else None,
                "sqft": int(row["sqft"]) if row.get("sqft") else None,
                "features": [f.strip() for f in (row.get("features") or "").split(";") if f.strip()],
                "description": (row.get("description") or "").strip(),
            }
            if not prop["title"]:
                raise ValueError("missing title")
            await asyncio.to_thread(rag_service.add_property, prop)
            inserted += 1
        except Exception as e:
            failed.append({"row": i, "error": str(e)})

    return {"status": "ok", "inserted": inserted, "failed": failed}


class KBDocumentIn(BaseModel):
    title: str
    content: str
    source: str = "manual"


@router.post("/api/kb")
async def add_kb_document(doc: KBDocumentIn):
    """Paste-in knowledge base entry (FAQ, policy, neighborhood guide, etc.)."""
    chunks = rag_service.chunk_text(doc.content)
    if len(chunks) <= 1:
        await asyncio.to_thread(rag_service.add_kb_document, doc.title, doc.content, doc.source)
        return {"status": "ok", "chunks_added": 1}

    for i, chunk in enumerate(chunks):
        await asyncio.to_thread(
            rag_service.add_kb_document, f"{doc.title} (part {i + 1})", chunk, doc.source
        )
    return {"status": "ok", "chunks_added": len(chunks)}


@router.post("/api/kb/upload")
async def upload_kb_file(file: UploadFile = File(...)):
    """
    Upload a plain-text (.txt/.md) knowledge file — it gets chunked and
    embedded the same way as a pasted entry. For PDFs, extract the text
    yourself first and paste it via /api/kb instead.
    """
    raw = (await file.read()).decode("utf-8", errors="ignore")
    chunks = rag_service.chunk_text(raw)
    for i, chunk in enumerate(chunks):
        await asyncio.to_thread(
            rag_service.add_kb_document, f"{file.filename} (part {i + 1})", chunk, file.filename
        )
    return {"status": "ok", "chunks_added": len(chunks)}


@router.get("/api/kb")
async def list_kb_documents():
    from database.supabase_client import get_supabase

    supabase = get_supabase()
    result = (
        supabase.table("kb_documents")
        .select("id, title, source, created_at")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []