from fastembed import TextEmbedding
from database.supabase_client import get_supabase
from config import settings

_embedder: TextEmbedding | None = None


def get_embedder() -> TextEmbedding:
    global _embedder
    if _embedder is None:
        _embedder = TextEmbedding(model_name=settings.EMBEDDING_MODEL)
    return _embedder


def embed_text(text: str) -> list[float]:
    embedder = get_embedder()
    vec = list(embedder.embed([text]))[0]
    return vec.tolist()


def _property_embedding_text(prop: dict) -> str:
    """Builds the text blob that gets embedded for a property listing."""
    parts = [
        prop.get("title", ""),
        prop.get("city", ""),
        prop.get("neighborhood", ""),
        f"{prop.get('bedrooms', '')} bedroom" if prop.get("bedrooms") else "",
        f"{prop.get('bathrooms', '')} bathroom" if prop.get("bathrooms") else "",
        " ".join(prop.get("features", []) or []),
        prop.get("description", ""),
    ]
    return " ".join(p for p in parts if p)


def add_property(prop: dict) -> dict:
    """
    Insert a property listing and embed it for RAG search.
    Expected keys: title, listing_type, address, city, neighborhood, price,
    bedrooms, bathrooms, sqft, features (list), description.
    """
    embedding = embed_text(_property_embedding_text(prop))
    supabase = get_supabase()
    payload = {**prop, "embedding": embedding}
    inserted = supabase.table("properties").insert(payload).execute()
    return inserted.data[0]


def retrieve_context(query: str, top_k: int = 4) -> str:
    """Return concatenated top-k relevant property listings as plain text context."""
    supabase = get_supabase()
    query_embedding = embed_text(query)

    try:
        result = supabase.rpc(
            "match_properties",
            {"query_embedding": query_embedding, "match_count": top_k},
        ).execute()
    except Exception:
        return ""

    rows = result.data or []
    if not rows:
        return ""

    chunks = []
    for row in rows:
        price = row.get("price")
        price_str = f"${price:,.0f}" if price else "price on request"
        chunks.append(
            f"### {row.get('title', 'Listing')} (id: {row.get('id')})\n"
            f"Type: {row.get('listing_type')} | City: {row.get('city')} / {row.get('neighborhood') or ''}\n"
            f"Price: {price_str} | Bedrooms: {row.get('bedrooms')} | Bathrooms: {row.get('bathrooms')} | Sqft: {row.get('sqft')}\n"
            f"Features: {', '.join(row.get('features') or [])}\n"
            f"{row.get('description', '')}"
        )

    return "\n\n".join(chunks)


def add_kb_document(title: str, content: str, source: str = "manual") -> None:
    """Add a general knowledge item (FAQ, neighborhood guide, policy text — not a property listing)."""
    embedding = embed_text(f"{title}\n{content}")
    supabase = get_supabase()
    supabase.table("kb_documents").insert(
        {"title": title, "content": content, "source": source, "embedding": embedding}
    ).execute()


def retrieve_kb_context(query: str, top_k: int = 3) -> str:
    """Return concatenated top-k relevant general knowledge chunks as plain text context."""
    supabase = get_supabase()
    query_embedding = embed_text(query)

    try:
        result = supabase.rpc(
            "match_kb_documents",
            {"query_embedding": query_embedding, "match_count": top_k},
        ).execute()
    except Exception:
        return ""

    rows = result.data or []
    if not rows:
        return ""

    chunks = []
    for row in rows:
        title = row.get("title") or "Untitled"
        content = row.get("content", "")
        chunks.append(f"### {title}\n{content}")

    return "\n\n".join(chunks)


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Kept for generic long-text ingestion (e.g. neighborhood guides, FAQs)."""
    words = text.split()
    chunks = []
    step = max(chunk_size - overlap, 1)
    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk:
            chunks.append(chunk)
        if i + chunk_size >= len(words):
            break
    return chunks
