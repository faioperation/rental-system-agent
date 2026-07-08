import uuid
from datetime import datetime, timedelta, timezone
from database.supabase_client import get_supabase


def generate_slots(property_id: str, days_ahead: int = 7, start_hour: int = 10, end_hour: int = 17) -> list[dict]:
    """
    Convenience helper for agents: auto-generates hourly viewing slots for a
    property over the next `days_ahead` days, between start_hour-end_hour
    (server local time / UTC — adjust as needed for your timezone).
    """
    supabase = get_supabase()
    now = datetime.now(timezone.utc)
    slots_to_insert = []

    for day_offset in range(days_ahead):
        day = (now + timedelta(days=day_offset + 1)).replace(minute=0, second=0, microsecond=0)
        for hour in range(start_hour, end_hour):
            slot_start = day.replace(hour=hour)
            slot_end = slot_start + timedelta(hours=1)
            slots_to_insert.append(
                {
                    "property_id": property_id,
                    "slot_start": slot_start.isoformat(),
                    "slot_end": slot_end.isoformat(),
                }
            )

    inserted = supabase.table("viewing_slots").insert(slots_to_insert).execute()
    return inserted.data or []


def get_available_slots(property_id: str, limit: int = 10) -> list[dict]:
    supabase = get_supabase()
    result = (
        supabase.table("viewing_slots")
        .select("*")
        .eq("property_id", property_id)
        .eq("is_booked", False)
        .gte("slot_start", datetime.now(timezone.utc).isoformat())
        .order("slot_start")
        .limit(limit)
        .execute()
    )
    return result.data or []


def book_viewing(
    slot_id: str,
    property_id: str,
    customer_id: str,
    conversation_id: str | None = None,
) -> dict | None:
    """Books a slot atomically-ish: checks it's still free, marks it booked, creates the viewing row."""
    supabase = get_supabase()

    slot = supabase.table("viewing_slots").select("*").eq("id", slot_id).eq("is_booked", False).execute()
    if not slot.data:
        return None  # already taken or doesn't exist

    slot_row = slot.data[0]
    supabase.table("viewing_slots").update({"is_booked": True}).eq("id", slot_id).execute()

    viewing = (
        supabase.table("viewings")
        .insert(
            {
                "slot_id": slot_id,
                "property_id": property_id,
                "customer_id": customer_id,
                "conversation_id": conversation_id,
                "scheduled_start": slot_row["slot_start"],
                "scheduled_end": slot_row["slot_end"],
            }
        )
        .execute()
    )
    return viewing.data[0]


def list_viewings(status: str | None = None) -> list[dict]:
    supabase = get_supabase()
    query = (
        supabase.table("viewings")
        .select("*, properties(title, address, city), customers(name, email, phone)")
        .order("scheduled_start")
    )
    if status:
        query = query.eq("status", status)
    return query.execute().data or []


def build_ics(viewing: dict, property_title: str, address: str) -> str:
    """
    Generates a minimal .ics calendar file for a confirmed viewing so the
    customer can add it to Google Calendar / Outlook / Apple Calendar
    without needing OAuth or any calendar API integration.
    """
    start = datetime.fromisoformat(viewing["scheduled_start"]).strftime("%Y%m%dT%H%M%SZ")
    end = datetime.fromisoformat(viewing["scheduled_end"]).strftime("%Y%m%dT%H%M%SZ")
    uid = str(uuid.uuid4())

    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Aria Real Estate Agent//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}\r\n"
        f"DTSTART:{start}\r\n"
        f"DTEND:{end}\r\n"
        f"SUMMARY:Property Viewing — {property_title}\r\n"
        f"LOCATION:{address or ''}\r\n"
        "DESCRIPTION:Scheduled via Aria real estate assistant.\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
