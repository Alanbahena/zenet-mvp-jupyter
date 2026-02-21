"""
LLM provider abstraction for Zenet MVP 0.1.

Provides: LlmProvider (abstract base), OpenAiProvider (concrete).
Pattern mirrors core/persistence.py: abstract interface + concrete implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from dotenv import load_dotenv

load_dotenv()

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
