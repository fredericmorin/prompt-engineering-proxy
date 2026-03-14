import re
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from ulid import ULID


def name_to_slug(name: str) -> str:
    """Convert a server display name to a URL-safe slug (lowercase alphanumeric + hyphens)."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "server"


def new_ulid() -> str:
    return str(ULID())


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class Server(BaseModel):
    id: str = Field(default_factory=new_ulid)
    name: str
    base_url: str
    protocol: str  # "openai_chat", "openai_responses", "anthropic", "ollama_chat", "ollama_generate"
    api_key: str | None = None
    proxy_slug: str | None = None  # custom URL prefix slug; falls back to name_to_slug(name) if None
    is_default: bool = False
    created_at: str = Field(default_factory=now_iso)


class ProxyRequest(BaseModel):
    id: str = Field(default_factory=new_ulid)
    server_id: str | None = None
    protocol: str
    method: str
    path: str
    request_headers: str  # JSON string
    request_body: str  # JSON string
    response_status: int | None = None
    response_headers: str | None = None
    response_body: str | None = None
    is_streaming: bool = False
    model: str | None = None
    duration_ms: int | None = None
    ttfb_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    error: str | None = None
    parent_id: str | None = None
    created_at: str = Field(default_factory=now_iso)


class RequestTag(BaseModel):
    request_id: str
    tag: str
