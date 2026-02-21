"""Unit tests for LLM framework (Task 4.1–4.3: OpenAiProvider, ClaudeProvider, ToolRegistry)."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.llm_framework import ClaudeProvider, LlmProvider, OpenAiProvider, ToolRegistry


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


class TestToolRegistry(unittest.TestCase):
    """Tests for ToolRegistry (Task 4.3)."""

    def test_register_and_to_openai_tools(self) -> None:
        """register + to_openai_tools returns correct structure."""
        def get_recipe(recipe_id: int) -> str:
            return f"recipe_{recipe_id}"

        registry = ToolRegistry()
        schema = {"type": "object", "properties": {"recipe_id": {"type": "integer"}}}
        registry.register("get_recipe", get_recipe, "Fetch a recipe by ID", schema)

        tools = registry.to_openai_tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["type"], "function")
        self.assertEqual(tools[0]["function"]["name"], "get_recipe")
        self.assertEqual(tools[0]["function"]["description"], "Fetch a recipe by ID")
        self.assertEqual(tools[0]["function"]["parameters"], schema)

    def test_to_openai_tools_default_schema(self) -> None:
        """register with parameters_schema=None uses default schema."""
        registry = ToolRegistry()
        registry.register("no_params", lambda: 42, "No params")

        tools = registry.to_openai_tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(
            tools[0]["function"]["parameters"],
            {"type": "object", "properties": {}},
        )

    def test_to_anthropic_tools(self) -> None:
        """to_anthropic_tools returns Anthropic format (no type wrapper)."""
        registry = ToolRegistry()
        registry.register("get_weather", lambda city: "sunny", "Get weather")

        tools = registry.to_anthropic_tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["name"], "get_weather")
        self.assertEqual(tools[0]["description"], "Get weather")
        self.assertEqual(
            tools[0]["input_schema"],
            {"type": "object", "properties": {}},
        )
        self.assertNotIn("type", tools[0])

    def test_execute_returns_value(self) -> None:
        """execute(name, arguments) returns function result."""
        mock_func = MagicMock(return_value="result")
        registry = ToolRegistry()
        registry.register("my_tool", mock_func, "My tool")

        result = registry.execute("my_tool", {"key": "value"})
        self.assertEqual(result, "result")
        mock_func.assert_called_once_with(key="value")

    def test_execute_with_none_arguments_defaults_to_empty(self) -> None:
        """execute(name, None) defaults to {} and calls func with no kwargs."""
        mock_func = MagicMock(return_value=0)
        registry = ToolRegistry()
        registry.register("no_args", mock_func, "No args")

        result = registry.execute("no_args", None)
        self.assertEqual(result, 0)
        mock_func.assert_called_once_with()

    def test_execute_unknown_name_raises(self) -> None:
        """execute(unknown_name) raises ValueError."""
        registry = ToolRegistry()
        with self.assertRaises(ValueError) as ctx:
            registry.execute("nonexistent", {})
        self.assertIn("Unknown tool", str(ctx.exception))
        self.assertIn("nonexistent", str(ctx.exception))

    def test_register_empty_name_raises(self) -> None:
        """register(name='', ...) raises ValueError."""
        registry = ToolRegistry()
        with self.assertRaises(ValueError) as ctx:
            registry.register("", lambda: None, "desc")
        self.assertIn("empty", str(ctx.exception).lower())

    def test_register_empty_description_raises(self) -> None:
        """register(..., description='') raises ValueError."""
        registry = ToolRegistry()
        with self.assertRaises(ValueError) as ctx:
            registry.register("tool", lambda: None, "")
        self.assertIn("empty", str(ctx.exception).lower())

    def test_multiple_tools_order_preserved(self) -> None:
        """Multiple tools: order preserved, both formats return length 2."""
        registry = ToolRegistry()
        registry.register("first", lambda: 1, "First")
        registry.register("second", lambda: 2, "Second")

        openai_tools = registry.to_openai_tools()
        anthropic_tools = registry.to_anthropic_tools()
        self.assertEqual(len(openai_tools), 2)
        self.assertEqual(len(anthropic_tools), 2)
        self.assertEqual(openai_tools[0]["function"]["name"], "first")
        self.assertEqual(openai_tools[1]["function"]["name"], "second")
        self.assertEqual(anthropic_tools[0]["name"], "first")
        self.assertEqual(anthropic_tools[1]["name"], "second")

    def test_duplicate_register_overwrites(self) -> None:
        """Register same name twice; second overwrites; execute calls second func."""
        first_func = MagicMock(return_value="first")
        second_func = MagicMock(return_value="second")
        registry = ToolRegistry()
        registry.register("tool", first_func, "First")
        registry.register("tool", second_func, "Second")

        result = registry.execute("tool", {})
        self.assertEqual(result, "second")
        first_func.assert_not_called()
        second_func.assert_called_once_with()

    def test_empty_registry_returns_empty_list(self) -> None:
        """Empty registry: to_openai_tools and to_anthropic_tools return []."""
        registry = ToolRegistry()
        self.assertEqual(registry.to_openai_tools(), [])
        self.assertEqual(registry.to_anthropic_tools(), [])


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
