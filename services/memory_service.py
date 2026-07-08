from datetime import datetime, timezone
from database.supabase_client import get_supabase
from config import settings


def get_or_create_customer(external_id: str | None, name: str | None, channel: str) -> dict:
    supabase = get_supabase()

    if external_id:
        existing = (
            supabase.table("customers")
            .select("*")
            .eq("external_id", external_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            return existing.data[0]

    inserted = (
        supabase.table("customers")
        .insert({"external_id": external_id, "name": name})
        .execute()
    )
    return inserted.data[0]


def get_or_create_conversation(conversation_id: str | None, customer_id: str, channel: str) -> dict:
    supabase = get_supabase()

    if conversation_id:
        existing = (
            supabase.table("conversations")
            .select("*")
            .eq("id", conversation_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            return existing.data[0]

    inserted = (
        supabase.table("conversations")
        .insert({"customer_id": customer_id, "channel": channel})
        .execute()
    )
    return inserted.data[0]


def save_message(
    conversation_id: str,
    role: str,
    content: str,
    intent: str | None = None,
    sentiment: str | None = None,
    sentiment_score: float | None = None,
    language: str | None = None,
) -> None:
    supabase = get_supabase()
    supabase.table("messages").insert(
        {
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "intent": intent,
            "sentiment": sentiment,
            "sentiment_score": sentiment_score,
            "language": language,
        }
    ).execute()

    supabase.table("conversations").update(
        {"last_message_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", conversation_id).execute()


def get_recent_history(conversation_id: str, limit: int = None) -> list[dict]:
    """Returns messages oldest-first, capped at settings.MAX_HISTORY_MESSAGES."""
    limit = limit or settings.MAX_HISTORY_MESSAGES
    supabase = get_supabase()
    result = (
        supabase.table("messages")
        .select("role, content")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = list(reversed(result.data or []))
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def get_conversations_by_external_id(external_id: str) -> list[dict]:
    supabase = get_supabase()
    customer = supabase.table("customers").select("id").eq("external_id", external_id).limit(1).execute()
    if not customer.data:
        return []
    
    customer_id = customer.data[0]["id"]
    result = (
        supabase.table("conversations")
        .select("id, started_at, last_message_at")
        .eq("customer_id", customer_id)
        .order("last_message_at", desc=True)
        .execute()
    )
    return result.data or []


def build_history_text(history: list[dict]) -> str:
    lines = []
    for turn in history:
        speaker = "Customer" if turn["role"] == "user" else "Agent"
        lines.append(f"{speaker}: {turn['content']}")
    return "\n".join(lines)


def get_customer_context(customer_id: str) -> str:
    """
    Builds a short text block summarizing customer profile + past ticket
    history, used to personalize responses (e.g. 'this customer had a
    billing issue last month').
    """
    supabase = get_supabase()

    customer = supabase.table("customers").select("*").eq("id", customer_id).limit(1).execute()
    if not customer.data:
        return ""
    c = customer.data[0]

    past_tickets = (
        supabase.table("tickets")
        .select("category, priority, status, summary, created_at")
        .eq("customer_id", customer_id)
        .order("created_at", desc=True)
        .limit(3)
        .execute()
    )

    lines = []
    if c.get("name"):
        lines.append(f"Name: {c['name']}")
    if c.get("tags"):
        lines.append(f"Tags: {', '.join(c['tags'])}")

    if past_tickets.data:
        lines.append("Recent past tickets:")
        for t in past_tickets.data:
            lines.append(
                f"- [{t['created_at'][:10]}] {t['category']} ({t['priority']}, {t['status']}): {t['summary']}"
            )

    return "\n".join(lines)
