from abc import ABC, abstractmethod


class ProtocolHandler(ABC):
    @property
    @abstractmethod
    def protocol_name(self) -> str: ...

    @property
    def streaming_format(self) -> str:
        """Return the streaming format: 'sse' (Server-Sent Events) or 'ndjson' (newline-delimited JSON)."""
        return "sse"

    @property
    def models_endpoint(self) -> str | None:
        """Relative URL path for listing models (e.g. '/v1/models'). None if unsupported."""
        return None

    def parse_models_response(self, data: dict[str, object]) -> list[dict[str, object]]:
        """Parse upstream model listing response into a normalized list with 'id' field."""
        return []

    @abstractmethod
    def extract_model(self, body: dict[str, object]) -> str | None: ...

    @abstractmethod
    def extract_usage(self, response_body: dict[str, object]) -> tuple[int | None, int | None]:
        """Return (prompt_tokens, completion_tokens) from a complete response body."""
        ...

    @abstractmethod
    def assemble_streaming_response(self, chunks: list[dict[str, object]]) -> dict[str, object]:
        """Assemble a full response dict from parsed stream chunks."""
        ...
