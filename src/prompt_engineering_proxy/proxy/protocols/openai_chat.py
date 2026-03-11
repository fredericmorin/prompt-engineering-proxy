from typing import cast

from prompt_engineering_proxy.proxy.protocols.base import ProtocolHandler


class OpenAIChatHandler(ProtocolHandler):
    @property
    def protocol_name(self) -> str:
        return "openai_chat"

    def extract_model(self, body: dict[str, object]) -> str | None:
        model = body.get("model")
        return str(model) if model is not None else None

    def extract_usage(self, response_body: dict[str, object]) -> tuple[int | None, int | None]:
        raw_usage = response_body.get("usage")
        if not isinstance(raw_usage, dict):
            return None, None
        # Cast to a typed dict so ty can resolve .get() correctly
        usage = cast(dict[str, object], raw_usage)
        pt = usage.get("prompt_tokens")
        ct = usage.get("completion_tokens")
        return (int(pt) if isinstance(pt, int) else None, int(ct) if isinstance(ct, int) else None)

    def assemble_streaming_response(self, chunks: list[dict[str, object]]) -> dict[str, object]:
        """Assemble a complete response from OpenAI Chat streaming delta chunks.

        OpenAI Chat stream format:
          data: {"id":"...", "choices":[{"delta":{"content":"..."}, "finish_reason":null}]}\n\n
          data: [DONE]\n\n
        """
        if not chunks:
            return {}

        result: dict[str, object] = dict(chunks[0])
        content = ""
        finish_reason: str | None = None

        for chunk in chunks:
            choices = chunk.get("choices")
            if not isinstance(choices, list):
                continue
            for raw_choice in choices:
                if not isinstance(raw_choice, dict):
                    continue
                choice = cast(dict[str, object], raw_choice)
                raw_delta = choice.get("delta")
                if isinstance(raw_delta, dict):
                    delta = cast(dict[str, object], raw_delta)
                    chunk_content = delta.get("content")
                    if isinstance(chunk_content, str):
                        content += chunk_content
                fr = choice.get("finish_reason")
                if fr is not None:
                    finish_reason = str(fr)

        result["choices"] = [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ]
        result.pop("object", None)
        result["object"] = "chat.completion"
        return result
