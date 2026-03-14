from typing import cast

from prompt_engineering_proxy.proxy.protocols.base import ProtocolHandler


class AnthropicHandler(ProtocolHandler):
    @property
    def protocol_name(self) -> str:
        return "anthropic"

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
        """Assemble a complete response from Anthropic Messages API streaming events.

        Anthropic stream format:
          event: message_start
          data: {"type":"message_start","message":{"id":"...","type":"message","role":"assistant",
                 "content":[],"model":"...","stop_reason":null,
                 "usage":{"input_tokens":25,"output_tokens":1}}}

          event: content_block_delta
          data: {"type":"content_block_delta","index":0,
                 "delta":{"type":"text_delta","text":"Hello"}}

          event: message_delta
          data: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},
                 "usage":{"output_tokens":10}}

          event: message_stop
          data: {"type":"message_stop"}
        """
        if not chunks:
            return {}

        # Extract base message structure from message_start
        base: dict[str, object] = {}
        for chunk in chunks:
            if chunk.get("type") == "message_start":
                message = chunk.get("message")
                if isinstance(message, dict):
                    base = dict(cast(dict[str, object], message))
                break

        if not base:
            return {}

        # Accumulate text per content block index
        text_blocks: dict[int, str] = {}
        for chunk in chunks:
            if chunk.get("type") == "content_block_delta":
                index = chunk.get("index")
                if not isinstance(index, int):
                    continue
                delta = chunk.get("delta")
                if not isinstance(delta, dict):
                    continue
                delta_dict = cast(dict[str, object], delta)
                if delta_dict.get("type") == "text_delta":
                    text = delta_dict.get("text")
                    if isinstance(text, str):
                        text_blocks[index] = text_blocks.get(index, "") + text

        # Apply message_delta (stop_reason + updated output_tokens)
        for chunk in chunks:
            if chunk.get("type") == "message_delta":
                delta = chunk.get("delta")
                if isinstance(delta, dict):
                    delta_dict = cast(dict[str, object], delta)
                    stop_reason = delta_dict.get("stop_reason")
                    if stop_reason is not None:
                        base["stop_reason"] = stop_reason
                usage = chunk.get("usage")
                if isinstance(usage, dict):
                    usage_dict = cast(dict[str, object], usage)
                    existing_usage = base.get("usage")
                    if isinstance(existing_usage, dict):
                        merged: dict[str, object] = dict(cast(dict[str, object], existing_usage))
                        merged.update(usage_dict)
                        base["usage"] = merged
                    else:
                        base["usage"] = dict(usage_dict)

        # Build content blocks from accumulated text
        content: list[dict[str, object]] = [
            {"type": "text", "text": text_blocks[idx]}
            for idx in sorted(text_blocks.keys())
        ]
        if not content:
            content = [{"type": "text", "text": ""}]
        base["content"] = content

        return base
