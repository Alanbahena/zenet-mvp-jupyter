"""Unit tests for LLM framework (Task 4.1 OpenAiProvider, Task 4.2 ClaudeProvider)."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.llm_framework import ClaudeProvider, LlmProvider, OpenAiProvider


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


class TestClaudeProvider(unittest.TestCase):
    """Tests with mocked Anthropic API."""

    @patch("core.llm_framework.Anthropic")
    def test_generate_returns_string(self, mock_anthropic_class: MagicMock) -> None:
        """ClaudeProvider().generate(prompt='Hi') returns string."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value.content = [
            MagicMock(type="text", text="Hello there!")
        ]
        mock_anthropic_class.return_value = mock_client

        provider = ClaudeProvider()
        result = provider.generate(prompt="Hi")

        self.assertEqual(result, "Hello there!")
        mock_client.messages.create.assert_called_once()

    @patch("core.llm_framework.Anthropic")
    def test_generate_with_system_passes_system_param(
        self, mock_anthropic_class: MagicMock
    ) -> None:
        """generate(prompt='Hi', system='You are helpful') passes system= param."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value.content = [
            MagicMock(type="text", text="Hi")
        ]
        mock_anthropic_class.return_value = mock_client

        provider = ClaudeProvider()
        provider.generate(prompt="Hi", system="You are helpful.")

        call_kwargs = mock_client.messages.create.call_args[1]
        self.assertEqual(call_kwargs.get("system"), "You are helpful.")
        msgs = call_kwargs["messages"]
        self.assertEqual(msgs, [{"role": "user", "content": "Hi"}])

    @patch("core.llm_framework.Anthropic")
    def test_generate_with_messages_filters_system(
        self, mock_anthropic_class: MagicMock
    ) -> None:
        """generate(messages=[...]) filters system role; passes user/assistant only."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value.content = [
            MagicMock(type="text", text="Hi")
        ]
        mock_anthropic_class.return_value = mock_client

        provider = ClaudeProvider()
        provider.generate(
            messages=[
                {"role": "system", "content": "Ignore"},
                {"role": "user", "content": "Hello"},
            ]
        )

        call_kwargs = mock_client.messages.create.call_args[1]
        self.assertEqual(call_kwargs["messages"], [{"role": "user", "content": "Hello"}])

    @patch("core.llm_framework.Anthropic")
    def test_generate_structured_output_appends_json_instruction(
        self, mock_anthropic_class: MagicMock
    ) -> None:
        """generate(prompt='Hi', structured_output=True) appends JSON instruction."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value.content = [
            MagicMock(type="text", text="{}")
        ]
        mock_anthropic_class.return_value = mock_client

        provider = ClaudeProvider()
        provider.generate(prompt="Hi", structured_output=True)

        call_kwargs = mock_client.messages.create.call_args[1]
        system = call_kwargs.get("system", "")
        self.assertIn("JSON", system)
        self.assertIn("valid JSON", system)

    @patch("core.llm_framework.Anthropic")
    def test_claude_provider_uses_custom_model(
        self, mock_anthropic_class: MagicMock
    ) -> None:
        """ClaudeProvider(model_name='claude-opus-4-6') uses custom model."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value.content = [
            MagicMock(type="text", text="Hi")
        ]
        mock_anthropic_class.return_value = mock_client

        provider = ClaudeProvider(model_name="claude-opus-4-6")
        provider.generate(prompt="Hi")

        call_kwargs = mock_client.messages.create.call_args[1]
        self.assertEqual(call_kwargs["model"], "claude-opus-4-6")

    @patch("core.llm_framework.Anthropic")
    def test_generate_with_tools_passes_tools_to_api(
        self, mock_anthropic_class: MagicMock
    ) -> None:
        """generate(prompt='Hi', tools=[...]) passes tools to API."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value.content = [
            MagicMock(type="text", text="Hi")
        ]
        mock_anthropic_class.return_value = mock_client

        tools = [
            {
                "name": "get_weather",
                "description": "Get weather",
                "input_schema": {"type": "object", "properties": {}},
            }
        ]
        provider = ClaudeProvider()
        provider.generate(prompt="Hi", tools=tools)

        call_kwargs = mock_client.messages.create.call_args[1]
        self.assertEqual(call_kwargs.get("tools"), tools)

    @patch("core.llm_framework.Anthropic")
    def test_generate_no_text_block_returns_empty_string(
        self, mock_anthropic_class: MagicMock
    ) -> None:
        """When response has no text block (e.g. tool_use only), return empty string."""
        mock_client = MagicMock()
        tool_use_block = SimpleNamespace(type="tool_use", name="get_weather", input={})
        mock_client.messages.create.return_value.content = [tool_use_block]
        mock_anthropic_class.return_value = mock_client

        provider = ClaudeProvider()
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

    @unittest.skipIf(
        not os.getenv("ANTHROPIC_API_KEY"),
        "No ANTHROPIC_API_KEY set",
    )
    def test_claude_provider_live_call(self) -> None:
        """ClaudeProvider().generate(prompt='Say hello') returns non-empty string."""
        provider = ClaudeProvider()
        result = provider.generate(prompt="Say hello in one word.")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)
