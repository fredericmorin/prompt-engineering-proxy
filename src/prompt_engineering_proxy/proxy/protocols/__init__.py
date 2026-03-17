"""Protocol handler registry — shared instances for all supported LLM protocols."""

from prompt_engineering_proxy.proxy.protocols.anthropic import AnthropicHandler
from prompt_engineering_proxy.proxy.protocols.base import ProtocolHandler
from prompt_engineering_proxy.proxy.protocols.ollama_chat import OllamaChatHandler
from prompt_engineering_proxy.proxy.protocols.ollama_generate import OllamaGenerateHandler
from prompt_engineering_proxy.proxy.protocols.openai_chat import OpenAIChatHandler
from prompt_engineering_proxy.proxy.protocols.openai_responses import OpenAIResponsesHandler

PROTOCOL_HANDLERS: dict[str, ProtocolHandler] = {
    "openai_chat": OpenAIChatHandler(),
    "openai_responses": OpenAIResponsesHandler(),
    "anthropic": AnthropicHandler(),
    "ollama_chat": OllamaChatHandler(),
    "ollama_generate": OllamaGenerateHandler(),
}

__all__ = ["PROTOCOL_HANDLERS", "ProtocolHandler"]
