"""
LLM provider abstraction for Zenet MVP 0.1.

Provides: LlmProvider (abstract base), OpenAiProvider, ClaudeProvider (concrete),
ToolRegistry for function calling.
Pattern mirrors core/persistence.py: abstract interface + concrete implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from anthropic import Anthropic
from openai import OpenAI


class LlmProvider(ABC):
    """Abstract base for LLM providers (OpenAI, Claude)."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def generate(
        self,
        *,
        prompt: str | None = None,
        system: str | None = None,
        tools: list | None = None,
        structured_output: bool = False,
        messages: list | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Validate input and delegate to _do_generate. Provide either prompt or messages."""
        self._validate_input(prompt, messages)
        return self._do_generate(
            prompt=prompt,
            system=system,
            tools=tools,
            structured_output=structured_output,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    @abstractmethod
    def _do_generate(
        self,
        *,
        prompt: str | None,
        system: str | None,
        tools: list | None,
        structured_output: bool,
        messages: list | None,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Provider-specific generation logic. Input is pre-validated."""
        ...

    def _validate_input(self, prompt: str | None, messages: list | None) -> None:
        if messages is None and not prompt:
            raise ValueError("Either prompt or messages must be provided")


class OpenAiProvider(LlmProvider):
    """OpenAI GPT provider. Uses OPENAI_API_KEY from environment."""

    def __init__(self, model_name: str = "gpt-4o") -> None:
        super().__init__(model_name)
        self.client = OpenAI()

    def _do_generate(
        self,
        *,
        prompt: str | None,
        system: str | None,
        tools: list | None,
        structured_output: bool,
        messages: list | None,
        max_tokens: int,
        temperature: float,
    ) -> str:
        if messages is not None:
            api_messages: list[dict[str, str]] = []
            if system:
                api_messages.append({"role": "system", "content": system})
            api_messages.extend(messages)
        else:
            api_messages = []
            if system:
                api_messages.append({"role": "system", "content": system})
            api_messages.append({"role": "user", "content": prompt or ""})

        kwargs: dict = {
            "model": self.model_name,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
        if structured_output:
            kwargs["response_format"] = {"type": "json_object"}

        response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        return content if content is not None else ""


class ClaudeProvider(LlmProvider):
    """Anthropic Claude provider. Uses ANTHROPIC_API_KEY from environment."""

    def __init__(self, model_name: str = "claude-sonnet-4-6") -> None:
        super().__init__(model_name)
        self.client = Anthropic()

    def _do_generate(
        self,
        *,
        prompt: str | None,
        system: str | None,
        tools: list | None,
        structured_output: bool,
        messages: list | None,
        max_tokens: int,
        temperature: float,
    ) -> str:
        if messages is not None:
            api_messages = [m for m in messages if m.get("role") != "system"]
        else:
            api_messages = [{"role": "user", "content": prompt or ""}]

        effective_system = system or ""
        if structured_output:
            json_instruction = " Respond with valid JSON only. Do not include markdown code fences."
            effective_system = (
                (effective_system + json_instruction).strip()
                if effective_system
                else "Respond with valid JSON only. Do not include markdown code fences."
            )

        kwargs: dict = {
            "model": self.model_name,
            "max_tokens": max_tokens,
            "messages": api_messages,
        }
        if effective_system:
            kwargs["system"] = effective_system
        kwargs["temperature"] = temperature
        if tools:
            kwargs["tools"] = tools

        response = self.client.messages.create(**kwargs)
        if not response.content:
            return ""
        for block in response.content:
            text = getattr(block, "text", None)
            if text:
                return text
        return ""


@dataclass
class _ToolEntry:
    name: str
    func: Callable[..., Any]
    description: str
    parameters_schema: dict[str, Any] | None


_DEFAULT_PARAMETERS_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}}


class ToolRegistry:
    """Provider-agnostic registry for LLM tools (function calling)."""

    def __init__(self) -> None:
        self._tools: dict[str, _ToolEntry] = {}

    def register(
        self,
        name: str,
        func: Callable[..., Any],
        description: str,
        parameters_schema: dict[str, Any] | None = None,
    ) -> None:
        """Register a tool. Duplicate name overwrites. Empty name/description raises ValueError."""
        if not name or not name.strip():
            raise ValueError("Tool name cannot be empty")
        if not description or not description.strip():
            raise ValueError("Tool description cannot be empty")
        self._tools[name] = _ToolEntry(
            name=name,
            func=func,
            description=description,
            parameters_schema=parameters_schema,
        )

    def to_openai_tools(self) -> list[dict[str, Any]]:
        """Return tools in OpenAI format."""
        result: list[dict[str, Any]] = []
        for entry in self._tools.values():
            schema = entry.parameters_schema or _DEFAULT_PARAMETERS_SCHEMA
            result.append(
                {
                    "type": "function",
                    "function": {
                        "name": entry.name,
                        "description": entry.description,
                        "parameters": schema,
                    },
                }
            )
        return result

    def to_anthropic_tools(self) -> list[dict[str, Any]]:
        """Return tools in Anthropic format."""
        result: list[dict[str, Any]] = []
        for entry in self._tools.values():
            schema = entry.parameters_schema or _DEFAULT_PARAMETERS_SCHEMA
            result.append(
                {
                    "name": entry.name,
                    "description": entry.description,
                    "input_schema": schema,
                }
            )
        return result

    def execute(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Execute a registered tool by name. Unknown name raises ValueError."""
        arguments = arguments or {}
        if name not in self._tools:
            raise ValueError(f"Unknown tool: {name}")
        return self._tools[name].func(**arguments)
