from pydantic import BaseModel, Field

from prompt_engineering_proxy.storage.models import now_iso

# Event types
REQUEST_STARTED = "request.started"
REQUEST_COMPLETED = "request.completed"
REQUEST_ERROR = "request.error"
REQUEST_STOPPED = "request.stopped"
STREAM_CHUNK = "chunk"

# Redis channel names
CHANNEL_REQUESTS = "proxy:requests"
CHANNEL_STREAM_PREFIX = "proxy:stream:"


class ProxyEvent(BaseModel):
    type: str
    request_id: str
    data: dict[str, object] | None = None
    timestamp: str = Field(default_factory=now_iso)
