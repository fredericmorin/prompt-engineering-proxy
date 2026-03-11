from datetime import UTC, datetime

from pydantic import BaseModel, Field
from ulid import ULID


def new_ulid() -> str:
    return str(ULID())


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class Server(BaseModel):
    id: str = Field(default_factory=new_ulid)
    name: str
    base_url: str
    protocol: str  # "openai_chat", "openai_responses", "anthropic"
    api_key: str | None = None
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
