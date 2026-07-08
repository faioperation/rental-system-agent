import json
from pathlib import Path
from groq import Groq
from config import settings

_client: Groq | None = None
_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system_prompt.txt"


def get_groq() -> Groq:
    global _client
    if _client is None:
        if not settings.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY not set. Copy .env.example to .env and fill it in.")
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


def load_system_prompt() -> str:
    """Reads prompts/system_prompt.txt fresh each call — edit it live, no restart needed."""
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "You are a helpful real estate assistant. Reply in the customer's language."


def _is_rate_limit_error(e: Exception) -> bool:
    msg = str(e).lower()
    return "rate_limit" in msg or "429" in msg


def stream_chat_response(
    user_message: str,
    history: list[dict],
    rag_context: str,
    customer_context: str,
    detected_language: str = "en",
):
    """
    Yields text chunks (Claude-style token-by-token) for the given turn.
    Tries the primary model first; on a rate-limit error, automatically
    retries once with the fallback model before giving up.
    """
    client = get_groq()

    context_block = ""
    if rag_context:
        context_block += f"\n\n[Available property listings — ONLY recommend from these]\n{rag_context}"
    if customer_context:
        context_block += f"\n\n[Customer profile / lead history]\n{customer_context}"

    context_block += (
        f"\n\n[Language instruction] Reply strictly in this language for this turn: "
        f"{detected_language}. Do not switch to any other language."
    )

    messages = [{"role": "system", "content": load_system_prompt() + context_block}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    models_to_try = [settings.GROQ_MODEL, settings.GROQ_FALLBACK_MODEL]

    for attempt, model in enumerate(models_to_try):
        try:
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.5,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
            return
        except Exception as e:
            is_last_attempt = attempt == len(models_to_try) - 1
            if _is_rate_limit_error(e) and not is_last_attempt:
                continue
            if _is_rate_limit_error(e):
                yield "Limit reached. Wait for sometime."
            else:
                yield "Sorry, something went wrong on our end. Please try again in a moment."
            return


def _json_completion(prompt: str, system: str) -> dict:
    client = get_groq()
    models_to_try = [settings.GROQ_MODEL, settings.GROQ_FALLBACK_MODEL]

    for attempt, model in enumerate(models_to_try):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
        except Exception as e:
            is_last_attempt = attempt == len(models_to_try) - 1
            if _is_rate_limit_error(e) and not is_last_attempt:
                continue
            return {}

    return {}


def analyze_message(message: str, history_text: str) -> dict:
    """Single structured call: intent, sentiment, language, lead temperature, escalation."""
    system = """You analyze a message sent to a real estate agency's AI assistant and return STRICT JSON only, no prose, matching this schema:
{
  "intent": "property_search|price_inquiry|viewing_request|financing_inquiry|legal_inquiry|complaint|general_inquiry",
  "sentiment": "positive|neutral|negative|frustrated",
  "sentiment_score": -1.0 to 1.0,
  "language": "en|bn|bn-en-mixed|fr|pt|ar|other",
  "lead_temperature": "cold|warm|hot",
  "should_escalate": true|false,
  "escalate_reason": "short reason or null"
}

Lead temperature guide:
- cold: general browsing, no specific area/budget/timeline yet
- warm: specific city/property type chosen, comparing options, has a rough budget or timeline
- hot: wants to view a specific property, has budget+location+bedrooms+timeline, asks about next steps to offer/apply, or requests a callback

Escalate to a human when: financing pre-approval questions, legal/contract questions, price negotiation, a complaint, or the customer explicitly asks for a human/callback."""

    prompt = f"Conversation so far (most recent last):\n{history_text}\n\nLatest customer message:\n{message}"
    result = _json_completion(prompt, system)

    return {
        "intent": result.get("intent", "general_inquiry"),
        "sentiment": result.get("sentiment", "neutral"),
        "sentiment_score": float(result.get("sentiment_score", 0.0) or 0.0),
        "language": result.get("language", "en"),
        "lead_temperature": result.get("lead_temperature", "cold"),
        "should_escalate": bool(result.get("should_escalate", False)),
        "escalate_reason": result.get("escalate_reason"),
    }


def classify_lead(conversation_text: str) -> dict:
    """
    Extract lead/property-search details and produce a category, priority,
    priority score, and a summary a human agent can scan in seconds.
    """
    system = """You are a lead-qualification assistant for a real estate agency. Read the full conversation and return STRICT JSON only:
{
  "category": "buy|rent|financing|legal|complaint|general",
  "priority": "low|medium|high|urgent",
  "priority_score": 0.0 to 1.0,
  "summary": "2-3 sentence summary for a human agent: what the customer wants, city/budget/bedrooms if known, lead temperature, and next step needed",
  "customer_name": "extracted name or null",
  "email": "extracted email or null",
  "phone": "extracted phone or null",
  "city": "extracted city or null",
  "neighborhood": "extracted neighborhood or null",
  "property_type": "extracted type (apartment/house/condo/etc.) or null",
  "bedrooms": "extracted number or null",
  "bathrooms": "extracted number or null",
  "budget_min": "extracted minimum budget or null",
  "budget_max": "extracted maximum budget or null",
  "move_in_timeline": "extracted timeline (e.g. 'within 2 weeks', 'next 3 months') or null",
  "must_have_features": "extracted comma-separated features or null"
}

Priority guidance: urgent = needs to move within 2 weeks or an active viewing/offer in progress; high = pre-approved financing + ready to view/offer, requests a callback, or investor/portfolio inquiry; medium = a normal qualified warm/hot lead with no urgency signals; low = cold lead just browsing."""

    result = _json_completion(conversation_text, system)

    return {
        "category": result.get("category", "general"),
        "priority": result.get("priority", "medium"),
        "priority_score": float(result.get("priority_score", 0.5) or 0.5),
        "summary": result.get("summary", ""),
        "lead_details": {
            k: result.get(k)
            for k in [
                "customer_name",
                "email",
                "phone",
                "city",
                "neighborhood",
                "property_type",
                "bedrooms",
                "bathrooms",
                "budget_min",
                "budget_max",
                "move_in_timeline",
                "must_have_features",
            ]
        },
    }
