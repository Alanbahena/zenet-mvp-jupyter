"""
LLM provider abstraction for Zenet MVP 0.1.

Provides: LlmProvider (abstract base), OpenAiProvider, ClaudeProvider (concrete),
ToolRegistry for function calling.
Pattern mirrors core/persistence.py: abstract interface + concrete implementations.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from anthropic import Anthropic
from openai import OpenAI


@dataclass
class ProviderResponse:
    """
    Rich response from provider.generate_raw().

    Exactly one of text or tool_calls will be set per response:
        text:       set when the LLM returns a final text answer.
        tool_calls: set when the LLM requests one or more tool executions.

    tool_calls format (normalized, provider-agnostic):
        [
            {
                "id": "call_abc123",
                "type": "function",
                "function": {
                    "name": "tool_name",
                    "arguments": '{"key": "value"}'  # always a JSON string
                }
            },
            ...
        ]

    arguments is always a JSON string (not a dict). This matches OpenAI native format
    and ensures round-trip consistency when messages are sent back to the API.
    Claude's input dict is serialized to a JSON string when building ProviderResponse.
    _execute_tool() in BaseAgent parses it back to a dict before calling the tool.
    """

    text: str | None = None
    tool_calls: list[dict[str, Any]] | None = None

    @property
    def has_tool_calls(self) -> bool:
        """True when the LLM returned tool call requests instead of a text response."""
        return bool(self.tool_calls)


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

    def generate_raw(
        self,
        *,
        prompt: str | None = None,
        system: str | None = None,
        tools: "ToolRegistry | None" = None,
        structured_output: bool = False,
        messages: list | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> ProviderResponse:
        """
        Generate a response and return a ProviderResponse (text or tool calls).

        Differs from generate() in two ways:
            1. tools accepts ToolRegistry | None instead of list | None.
               Each provider calls .to_openai_tools() or .to_anthropic_tools() internally.
            2. Returns ProviderResponse instead of str, surfacing tool call data
               that generate() discards.

        Default implementation: text-only fallback that wraps _do_generate().
        Providers that support tool calling MUST override this method.

        Note: The default passes tools=None to _do_generate() because ToolRegistry
        is incompatible with the list type expected there. A provider using the
        default will silently ignore any registered tools -- this is intentional
        to allow graceful degradation for providers that do not implement tool support.
        """
        self._validate_input(prompt, messages)
        text = self._do_generate(
            prompt=prompt,
            system=system,
            tools=None,
            structured_output=structured_output,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return ProviderResponse(text=text)


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

    def generate_raw(
        self,
        *,
        prompt: str | None = None,
        system: str | None = None,
        tools: "ToolRegistry | None" = None,
        structured_output: bool = False,
        messages: list | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> ProviderResponse:
        """
        Generate with native OpenAI tool calling support.

        When the LLM returns tool calls: normalizes to provider-agnostic format
        with arguments kept as a JSON string (OpenAI native format, no conversion).
        When the LLM returns text: returns ProviderResponse(text=...).
        """
        self._validate_input(prompt, messages)

        if messages is not None:
            api_messages: list[dict] = []
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
            kwargs["tools"] = tools.to_openai_tools()
        if structured_output:
            kwargs["response_format"] = {"type": "json_object"}

        response = self.client.chat.completions.create(**kwargs)
        msg = response.choices[0].message

        if msg.tool_calls:
            normalized = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,  # already a JSON string
                    },
                }
                for tc in msg.tool_calls
            ]
            return ProviderResponse(tool_calls=normalized)

        return ProviderResponse(text=msg.content if msg.content is not None else "")


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

    def _normalize_messages(self, messages: list[dict]) -> list[dict]:
        """
        Convert OpenAI-format messages to Claude API format.

        Handles:
            1. Filters system role messages (Claude uses system= parameter instead).
            2. Converts assistant tool_calls messages to Claude tool_use format.
            3. Converts tool role messages to Claude tool_result format.
            4. Merges consecutive tool role messages into a single user message
               (Claude API requirement: all results from one turn = one user message).
        """
        result: list[dict] = []
        i = 0
        while i < len(messages):
            msg = messages[i]
            role = msg.get("role")

            if role == "system":
                i += 1
                continue

            if role == "assistant" and msg.get("tool_calls"):
                content_blocks = []
                for tc in msg["tool_calls"]:
                    args = tc["function"]["arguments"]
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": args,
                    })
                result.append({"role": "assistant", "content": content_blocks})
                i += 1
                continue

            if role == "tool":
                # Collect all consecutive tool messages; merge into one user message.
                tool_result_blocks = []
                while i < len(messages) and messages[i].get("role") == "tool":
                    t = messages[i]
                    tool_result_blocks.append({
                        "type": "tool_result",
                        "tool_use_id": t["tool_call_id"],
                        "content": t["content"],
                    })
                    i += 1
                result.append({"role": "user", "content": tool_result_blocks})
                continue

            result.append(msg)
            i += 1

        return result

    def generate_raw(
        self,
        *,
        prompt: str | None = None,
        system: str | None = None,
        tools: "ToolRegistry | None" = None,
        structured_output: bool = False,
        messages: list | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> ProviderResponse:
        """
        Generate with native Anthropic Claude tool calling support.

        Normalizes incoming messages to Claude format via _normalize_messages() before
        the API call. Detects tool_use blocks in the response and normalizes to the
        provider-agnostic format. arguments in ProviderResponse is always a JSON string
        (Claude's input dict is serialized via json.dumps).
        """
        self._validate_input(prompt, messages)

        if messages is not None:
            api_messages = self._normalize_messages(messages)
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
            "temperature": temperature,
        }
        if effective_system:
            kwargs["system"] = effective_system
        if tools:
            kwargs["tools"] = tools.to_anthropic_tools()

        response = self.client.messages.create(**kwargs)

        tool_use_blocks = [
            b for b in response.content if getattr(b, "type", None) == "tool_use"
        ]
        if tool_use_blocks:
            normalized = [
                {
                    "id": b.id,
                    "type": "function",
                    "function": {
                        "name": b.name,
                        "arguments": json.dumps(b.input),  # dict -> JSON string
                    },
                }
                for b in tool_use_blocks
            ]
            return ProviderResponse(tool_calls=normalized)

        for block in response.content:
            text = getattr(block, "text", None)
            if text:
                return ProviderResponse(text=text)
        return ProviderResponse(text="")


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
