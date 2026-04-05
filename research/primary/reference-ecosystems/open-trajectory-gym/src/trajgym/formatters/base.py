"""Abstract base class for model-specific message formatters."""

from abc import ABC, abstractmethod
from typing import Any


class ModelFormatter(ABC):
    """Base class for model-specific message formatters.

    Each model family (Qwen3/Nanbeige, GLM-4, Devstral/Mistral) has its
    own chat template and tool-calling convention.  Concrete subclasses translate
    the canonical OpenAI-style message list into the model-native text
    representation used during training and inference.

    Usage::

        formatter = ModelFormatter.from_model_id("Qwen/Qwen3-8B")
        text = formatter.format_messages(messages)
        tools = formatter.get_tool_definitions()
    """

    def __init__(self, tokenizer: Any | None = None) -> None:
        self.tokenizer = tokenizer

    # ── Factory ───────────────────────────────────────────────────────

    @classmethod
    def from_model_id(
        cls,
        model_id: str,
        tokenizer: Any | None = None,
    ) -> "ModelFormatter":
        """Auto-detect model family and return the appropriate formatter.

        Parameters
        ----------
        model_id:
            HuggingFace model ID or a local path containing the model name.
        tokenizer:
            Optional pre-loaded tokenizer.  When provided, formatters that
            support ``tokenizer.apply_chat_template`` will prefer it.
        """
        model_lower = model_id.lower()

        # Nanbeige uses ChatML + Hermes tool calling (same as Qwen3).
        if any(k in model_lower for k in ("qwen", "openthinker", "nanbeige")):
            from .qwen3 import Qwen3Formatter

            return Qwen3Formatter(tokenizer)

        if "glm" in model_lower:
            from .glm4 import GLM4Formatter

            return GLM4Formatter(tokenizer)

        if any(k in model_lower for k in ("devstral", "mistral")):
            from .devstral import DevstralFormatter

            return DevstralFormatter(tokenizer)

        # Default: try ChatML/Hermes format (works for most Llama-family models).
        from .qwen3 import Qwen3Formatter

        return Qwen3Formatter(tokenizer)

    # ── Abstract interface ────────────────────────────────────────────

    @abstractmethod
    def format_messages(self, messages: list[dict[str, Any]]) -> str:
        """Convert an OpenAI-style message list into a model-native string.

        The returned string is suitable for tokenisation and training.
        """
        ...

    @abstractmethod
    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return BoxPwnr tool definitions in the model-native format.

        Most models accept the OpenAI function-calling schema directly;
        override this method when the model requires a different layout.
        """
        ...
