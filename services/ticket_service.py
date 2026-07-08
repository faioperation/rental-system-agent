from database.supabase_client import get_supabase
from services.groq_service import classify_lead


def create_or_update_ticket(
    conversation_id: str,
    customer_id: str,
    conversation_text: str,
    escalated: bool = False,
    escalated_reason: str | None = None,
) -> dict:
    supabase = get_supabase()
    classification = classify_lead(conversation_text)

    existing = (
        supabase.table("tickets")
        .select("id")
        .eq("conversation_id", conversation_id)
        .limit(1)
        .execute()
    )

    payload = {
        "conversation_id": conversation_id,
        "customer_id": customer_id,
        "category": classification["category"],
        "priority": classification["priority"],
        "priority_score": classification["priority_score"],
        "summary": classification["summary"],
        "escalated": escalated,
        "escalated_reason": escalated_reason,
    }

    if existing.data:
        ticket_id = existing.data[0]["id"]
        supabase.table("tickets").update(payload).eq("id", ticket_id).execute()
        payload["id"] = ticket_id
    else:
        inserted = supabase.table("tickets").insert(payload).execute()
        payload["id"] = inserted.data[0]["id"]

    # Store extracted lead details (name/email/city/budget/etc.) on the
    # customer profile so future turns can personalize using this history
    lead_details = {k: v for k, v in classification.get("lead_details", {}).items() if v}
    if lead_details:
        supabase.table("customers").update({"metadata": lead_details}).eq(
            "id", customer_id
        ).execute()

    if escalated:
        supabase.table("conversations").update({"status": "escalated"}).eq(
            "id", conversation_id
        ).execute()

    return payload


def list_tickets(status: str | None = None, priority: str | None = None) -> list[dict]:
    supabase = get_supabase()
    query = supabase.table("tickets").select("*").order("created_at", desc=True)
    if status:
        query = query.eq("status", status)
    if priority:
        query = query.eq("priority", priority)
    return query.execute().data or []
