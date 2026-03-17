from typing import cast

from prompt_engineering_proxy.proxy.protocols.base import ProtocolHandler


class OllamaChatHandler(ProtocolHandler):
    @property
    def protocol_name(self) -> str:
        return "ollama_chat"

    @property
    def streaming_format(self) -> str:
        return "ndjson"

    @property
    def models_endpoint(self) -> str | None:
        return "/api/tags"

    def parse_models_response(self, data: dict[str, object]) -> list[dict[str, object]]:
        raw = data.get("models", [])
        if not isinstance(raw, list):
            return []
        result: list[dict[str, object]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            m = cast(dict[str, object], item)
            name = m.get("name") or m.get("model") or ""
            result.append({**m, "id": str(name)})
        return result

    def extract_model(self, body: dict[str, object]) -> str | None:
        model = body.get("model")
        return str(model) if model is not None else None

    def extract_usage(self, response_body: dict[str, object]) -> tuple[int | None, int | None]:
        pt = response_body.get("prompt_eval_count")
        ct = response_body.get("eval_count")
        return (int(pt) if isinstance(pt, int) else None, int(ct) if isinstance(ct, int) else None)

    def assemble_streaming_response(self, chunks: list[dict[str, object]]) -> dict[str, object]:
        """Assemble a complete response from Ollama chat NDJSON stream chunks.

        Ollama chat stream format (newline-delimited JSON):
          {"model":"...","message":{"role":"assistant","content":"Hello"},"done":false}
          {"model":"...","message":{"role":"assistant","content":""},"done":true,"done_reason":"stop",...}
        """
        if not chunks:
            return {}

        content = ""
        final_chunk: dict[str, object] = {}

        for chunk in chunks:
            msg = chunk.get("message")
            if isinstance(msg, dict):
                msg_dict = cast(dict[str, object], msg)
                chunk_content = msg_dict.get("content")
                if isinstance(chunk_content, str):
                    content += chunk_content
            if chunk.get("done"):
                final_chunk = dict(chunk)

        result = final_chunk or dict(chunks[0])
        result["message"] = {"role": "assistant", "content": content}
        return result
