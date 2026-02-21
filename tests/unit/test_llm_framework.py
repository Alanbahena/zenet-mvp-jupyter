"""Unit tests for LLM framework (Task 4.1: LlmProvider, OpenAiProvider)."""

import os
import unittest
from unittest.mock import MagicMock, patch

from core.llm_framework import LlmProvider, OpenAiProvider


class TestOpenAiProvider(unittest.TestCase):
    """Tests with mocked OpenAI API."""

    @patch("core.llm_framework.OpenAI")
    def test_generate_returns_string(self, mock_openai_class: MagicMock) -> None:
        """OpenAiProvider().generate(prompt='Hi') returns string."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="Hello there!"))
        ]
        mock_openai_class.return_value = mock_client

        provider = OpenAiProvider()
        result = provider.generate(prompt="Hi")

        self.assertEqual(result, "Hello there!")
        mock_client.chat.completions.create.assert_called_once()

    def test_generate_prompt_none_messages_none_raises(self) -> None:
        """generate(prompt=None, messages=None) raises ValueError."""
        provider = OpenAiProvider()
        with self.assertRaises(ValueError) as ctx:
            provider.generate(prompt=None, messages=None)
        self.assertIn("Either prompt or messages must be provided", str(ctx.exception))

    def test_generate_prompt_empty_messages_none_raises(self) -> None:
        """generate(prompt='', messages=None) raises ValueError."""
        provider = OpenAiProvider()
        with self.assertRaises(ValueError) as ctx:
            provider.generate(prompt="", messages=None)
        self.assertIn("Either prompt or messages must be provided", str(ctx.exception))

    @patch("core.llm_framework.OpenAI")
    def test_generate_with_messages_uses_messages_ignores_prompt(
        self, mock_openai_class: MagicMock
    ) -> None:
        """generate(messages=[...]) uses messages, ignores prompt."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="Hi"))
        ]
        mock_openai_class.return_value = mock_client

        provider = OpenAiProvider()
        provider.generate(
            prompt="ignored",
            messages=[{"role": "user", "content": "Hello"}],
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        self.assertEqual(call_kwargs["messages"], [{"role": "user", "content": "Hello"}])

    @patch("core.llm_framework.OpenAI")
    def test_generate_with_system_prepends_system_message(
        self, mock_openai_class: MagicMock
    ) -> None:
        """generate(prompt='Hi', system='You are helpful') prepends system message."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="Hi"))
        ]
        mock_openai_class.return_value = mock_client

        provider = OpenAiProvider()
        provider.generate(prompt="Hi", system="You are helpful.")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        msgs = call_kwargs["messages"]
        self.assertEqual(msgs[0], {"role": "system", "content": "You are helpful."})
        self.assertEqual(msgs[1], {"role": "user", "content": "Hi"})

    @patch("core.llm_framework.OpenAI")
    def test_generate_structured_output_adds_response_format(
        self, mock_openai_class: MagicMock
    ) -> None:
        """generate(prompt='Hi', structured_output=True) adds response_format."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="{}"))
        ]
        mock_openai_class.return_value = mock_client

        provider = OpenAiProvider()
        provider.generate(prompt="Hi", structured_output=True)

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        self.assertEqual(
            call_kwargs.get("response_format"),
            {"type": "json_object"},
        )

    @patch("core.llm_framework.OpenAI")
    def test_openai_provider_uses_custom_model_name(
        self, mock_openai_class: MagicMock
    ) -> None:
        """OpenAiProvider(model_name='gpt-4-turbo') uses custom model."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="Hi"))
        ]
        mock_openai_class.return_value = mock_client

        provider = OpenAiProvider(model_name="gpt-4-turbo")
        provider.generate(prompt="Hi")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        self.assertEqual(call_kwargs["model"], "gpt-4-turbo")

    @patch("core.llm_framework.OpenAI")
    def test_generate_with_tools_passes_tools_to_api(
        self, mock_openai_class: MagicMock
    ) -> None:
        """generate(prompt='Hi', tools=[...]) passes tools to API."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="Hi"))
        ]
        mock_openai_class.return_value = mock_client

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_recipe",
                    "description": "Fetch a recipe",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        provider = OpenAiProvider()
        provider.generate(prompt="Hi", tools=tools)

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        self.assertEqual(call_kwargs.get("tools"), tools)

    @patch("core.llm_framework.OpenAI")
    def test_generate_content_none_returns_empty_string(
        self, mock_openai_class: MagicMock
    ) -> None:
        """When message.content is None (e.g. tool call), return empty string."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content=None))
        ]
        mock_openai_class.return_value = mock_client

        provider = OpenAiProvider()
        result = provider.generate(prompt="Hi")

        self.assertEqual(result, "")


class TestLiveProviders(unittest.TestCase):
    """Live integration tests (skipped if no API key)."""

    @unittest.skipIf(
        not os.getenv("OPENAI_API_KEY"),
        "No OPENAI_API_KEY set",
    )
    def test_openai_provider_live_call(self) -> None:
        """OpenAiProvider().generate(prompt='Say hello') returns non-empty string."""
        provider = OpenAiProvider()
        result = provider.generate(prompt="Say hello in one word.")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)
