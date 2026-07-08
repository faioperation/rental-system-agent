import asyncio
from fastapi import APIRouter, Response
from pydantic import BaseModel

from services import viewing_service

router = APIRouter(prefix="/api/viewings", tags=["viewings"])


@router.get("/available-slots/{property_id}")
async def available_slots(property_id: str):
    return await asyncio.to_thread(viewing_service.get_available_slots, property_id)


class GenerateSlotsIn(BaseModel):
    property_id: str
    days_ahead: int = 7
    start_hour: int = 10
    end_hour: int = 17


@router.post("/generate-slots")
async def generate_slots(body: GenerateSlotsIn):
    slots = await asyncio.to_thread(
        viewing_service.generate_slots, body.property_id, body.days_ahead, body.start_hour, body.end_hour
    )
    return {"status": "ok", "slots_created": len(slots)}


class BookViewingIn(BaseModel):
    slot_id: str
    property_id: str
    customer_external_id: str
    conversation_id: str | None = None


@router.post("/book")
async def book_viewing(body: BookViewingIn):
    from services import memory_service

    customer = await asyncio.to_thread(
        memory_service.get_or_create_customer, body.customer_external_id, None, "web"
    )
    viewing = await asyncio.to_thread(
        viewing_service.book_viewing, body.slot_id, body.property_id, customer["id"], body.conversation_id
    )
    if viewing is None:
        return Response(content='{"error": "Slot no longer available"}', status_code=409, media_type="application/json")
    return viewing


@router.get("/")
async def list_viewings(status: str | None = None):
    return await asyncio.to_thread(viewing_service.list_viewings, status)


@router.get("/{viewing_id}/ics")
async def download_ics(viewing_id: str):
    from database.supabase_client import get_supabase

    supabase = get_supabase()
    result = (
        supabase.table("viewings")
        .select("*, properties(title, address)")
        .eq("id", viewing_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return Response(content="Not found", status_code=404)

    viewing = result.data[0]
    prop = viewing.get("properties") or {}
    ics_content = viewing_service.build_ics(viewing, prop.get("title", "Property"), prop.get("address", ""))

    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="viewing-{viewing_id[:8]}.ics"'},
    )
