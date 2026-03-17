from typing import cast

from prompt_engineering_proxy.proxy.protocols.base import ProtocolHandler


class OpenAIResponsesHandler(ProtocolHandler):
    @property
    def protocol_name(self) -> str:
        return "openai_responses"

    @property
    def models_endpoint(self) -> str | None:
        return "/v1/models"

    def parse_models_response(self, data: dict[str, object]) -> list[dict[str, object]]:
        raw = data.get("data", [])
        if not isinstance(raw, list):
            return []
        return [cast(dict[str, object], m) for m in raw if isinstance(m, dict)]

    def extract_model(self, body: dict[str, object]) -> str | None:
        model = body.get("model")
        return str(model) if model is not None else None

    def extract_usage(self, response_body: dict[str, object]) -> tuple[int | None, int | None]:
        raw_usage = response_body.get("usage")
        if not isinstance(raw_usage, dict):
            return None, None
        usage = cast(dict[str, object], raw_usage)
        pt = usage.get("input_tokens")
        ct = usage.get("output_tokens")
        return (int(pt) if isinstance(pt, int) else None, int(ct) if isinstance(ct, int) else None)

    def assemble_streaming_response(self, chunks: list[dict[str, object]]) -> dict[str, object]:
        """Assemble a complete response from OpenAI Responses API streaming events.

        OpenAI Responses stream format:
          event: response.created
          data: {"type":"response.created","response":{"id":"...","status":"in_progress",...}}

          event: response.output_text.delta
          data: {"type":"response.output_text.delta","output_index":0,"content_index":0,"delta":"Hello"}

          event: response.completed
          data: {"type":"response.completed","response":{...full response...}}
        """
        if not chunks:
            return {}

        # Prefer the full response from response.completed or response.done events
        for chunk in reversed(chunks):
            event_type = chunk.get("type")
            if event_type in ("response.completed", "response.done"):
                response = chunk.get("response")
                if isinstance(response, dict):
                    return cast(dict[str, object], response)

        # Fallback: reconstruct from incremental delta events
        base: dict[str, object] = {}
        for chunk in chunks:
            if chunk.get("type") == "response.created":
                response = chunk.get("response")
                if isinstance(response, dict):
                    base = dict(cast(dict[str, object], response))
                break

        text = ""
        for chunk in chunks:
            if chunk.get("type") == "response.output_text.delta":
                delta = chunk.get("delta")
                if isinstance(delta, str):
                    text += delta

        if base:
            base["output"] = [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": text, "annotations": []}],
                }
            ]
            base["status"] = "completed"
            return base

        return {
            "type": "response",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": text, "annotations": []}],
                }
            ],
        }
