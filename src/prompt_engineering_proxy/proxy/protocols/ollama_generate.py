from prompt_engineering_proxy.proxy.protocols.base import ProtocolHandler


class OllamaGenerateHandler(ProtocolHandler):
    @property
    def protocol_name(self) -> str:
        return "ollama_generate"

    @property
    def streaming_format(self) -> str:
        return "ndjson"

    def extract_model(self, body: dict[str, object]) -> str | None:
        model = body.get("model")
        return str(model) if model is not None else None

    def extract_usage(self, response_body: dict[str, object]) -> tuple[int | None, int | None]:
        pt = response_body.get("prompt_eval_count")
        ct = response_body.get("eval_count")
        return (int(pt) if isinstance(pt, int) else None, int(ct) if isinstance(ct, int) else None)

    def assemble_streaming_response(self, chunks: list[dict[str, object]]) -> dict[str, object]:
        """Assemble a complete response from Ollama generate NDJSON stream chunks.

        Ollama generate stream format (newline-delimited JSON):
          {"model":"...","response":"Hello","done":false}
          {"model":"...","response":"","done":true,"done_reason":"stop",...}
        """
        if not chunks:
            return {}

        response_text = ""
        final_chunk: dict[str, object] = {}

        for chunk in chunks:
            token = chunk.get("response")
            if isinstance(token, str):
                response_text += token
            if chunk.get("done"):
                final_chunk = dict(chunk)

        result = final_chunk or dict(chunks[0])
        result["response"] = response_text
        return result
