from supabase import create_client, Client
from config import settings

_client: Client | None = None


def get_supabase() -> Client:
    """Return a cached Supabase client instance."""
    global _client
    if _client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise RuntimeError(
                "SUPABASE_URL / SUPABASE_KEY not set. Copy .env.example to .env and fill them in."
            )
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    return _client
