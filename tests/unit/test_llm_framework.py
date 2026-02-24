"""Unit tests for LLM framework (Task 4.1–4.3: OpenAiProvider, ClaudeProvider, ToolRegistry)."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.ai.providers import ClaudeProvider, LlmProvider, OpenAiProvider, ToolRegistry


class TestOpenAiProvider(unittest.TestCase):
    """Tests with mocked OpenAI API."""

    @patch("core.ai.providers.OpenAI")
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

    @patch("core.ai.providers.OpenAI")
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

    @patch("core.ai.providers.OpenAI")
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

    @patch("core.ai.providers.OpenAI")
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

    @patch("core.ai.providers.OpenAI")
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

    @patch("core.ai.providers.OpenAI")
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

    @patch("core.ai.providers.OpenAI")
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

    @patch("core.ai.providers.Anthropic")
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

    @patch("core.ai.providers.Anthropic")
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

    @patch("core.ai.providers.Anthropic")
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

    @patch("core.ai.providers.Anthropic")
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

    @patch("core.ai.providers.Anthropic")
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

    @patch("core.ai.providers.Anthropic")
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

    @patch("core.ai.providers.Anthropic")
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


# =============================================================================
# Live Integration Tests (Subtask 4.7)
# =============================================================================
# These tests make REAL API calls to OpenAI and Anthropic.
# They are skipped if API keys are not set in the environment.
#
# Cost per full run: ~$0.01 with default lightweight models
#
# Run with: pytest tests/unit/ -k Live -v

from core.ai.utils import parse_structured_output


class TestLiveOpenAiProvider(unittest.TestCase):
    """
    Live integration tests with real OpenAI API.

    These tests make REAL API calls to OpenAI. They are skipped if
    OPENAI_API_KEY is not set in the environment.

    Model: Controlled by TEST_OPENAI_MODEL env var (default: gpt-4o-mini).
    Cost: ~$0.005 per full test run with default model.

    Override model for one-time testing:
        TEST_OPENAI_MODEL=gpt-4o pytest tests/unit/ -k LiveOpenAi
    """

    def setUp(self):
        """Set up provider with test model from environment."""
        if os.getenv("OPENAI_API_KEY"):
            # Default to mini for cost savings, allow override
            test_model = os.getenv("TEST_OPENAI_MODEL", "gpt-4o-mini")
            self.provider = OpenAiProvider(model_name=test_model)

    @unittest.skipIf(not os.getenv("OPENAI_API_KEY"), "No OpenAI API key")
    def test_live_generate_simple_prompt(self):
        """
        Verify OpenAiProvider can make a real API call and return a response.

        This test makes ONE real API call to OpenAI.
        Expected cost: ~$0.0002 with gpt-4o-mini.
        """
        response = self.provider.generate(prompt=
            "What is 2+2? Answer with just the number.",
            temperature=0  # Deterministic
        )

        # Assertions (robust, non-deterministic friendly)
        self.assertIsNotNone(response)
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 0)
        self.assertIn("4", response)

    @unittest.skipIf(not os.getenv("OPENAI_API_KEY"), "No OpenAI API key")
    def test_live_generate_with_system(self):
        """
        Verify system message is properly injected into OpenAI API call.

        OpenAI expects system as a message with role="system".
        """
        response = self.provider.generate(prompt=
            "What is 5+3?",
            system="You are a helpful math tutor. Always explain your answers.",
            temperature=0
        )

        self.assertIsNotNone(response)
        self.assertIn("8", response)
        # System prompt should make response more verbose/explanatory
        self.assertGreater(len(response), 5)

    @unittest.skipIf(not os.getenv("OPENAI_API_KEY"), "No OpenAI API key")
    def test_live_generate_structured_output(self):
        """
        Verify JSON mode (structured_output=True) works with real API.

        OpenAI uses response_format={"type": "json_object"} for JSON mode.
        """
        prompt = (
            "Return a JSON object with these exact keys: "
            "'name' (set to 'test'), 'value' (set to 42), 'active' (set to true)."
        )

        response = self.provider.generate(prompt=
            prompt,
            structured_output=True,
            temperature=0
        )

        # Parse and validate
        data = parse_structured_output(response)
        self.assertIsInstance(data, dict)
        self.assertEqual(data.get("name"), "test")
        self.assertEqual(data.get("value"), 42)
        self.assertEqual(data.get("active"), True)

    @unittest.skipIf(not os.getenv("OPENAI_API_KEY"), "No OpenAI API key")
    def test_live_generate_with_tools(self):
        """
        Verify tool calling (function calling) works with real API.

        Tests that OpenAI properly receives and invokes tools.
        """
        # Simple calculator tool
        registry = ToolRegistry()

        def add(a: int, b: int) -> int:
            return a + b

        registry.register(
            "add",
            add,
            description="Add two numbers",
            parameters_schema={
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"}
                },
                "required": ["a", "b"]
            }
        )

        response = self.provider.generate(prompt=
            "Use the add tool to calculate 10 + 15",
            tools=registry.to_openai_tools(),
            temperature=0
        )

        # Response should be non-empty (tool usage or result)
        self.assertIsNotNone(response)
        self.assertIsInstance(response, str)

    @unittest.skipIf(not os.getenv("OPENAI_API_KEY"), "No OpenAI API key")
    def test_live_multi_turn_with_messages(self):
        """
        Verify multi-turn conversation with messages parameter.

        Tests that the provider correctly handles the messages list
        for context preservation.
        """
        messages = [
            {"role": "user", "content": "My name is Alice."},
            {"role": "assistant", "content": "Nice to meet you, Alice!"},
            {"role": "user", "content": "What is my name?"}
        ]

        response = self.provider.generate(
            prompt=None,  # Not used when messages provided
            messages=messages,
            temperature=0
        )

        # Should remember name from earlier message
        self.assertIn("Alice", response)


class TestLiveClaudeProvider(unittest.TestCase):
    """
    Live integration tests with real Anthropic API.

    These tests make REAL API calls to Anthropic. They are skipped if
    ANTHROPIC_API_KEY is not set in the environment.

    Model: Controlled by TEST_ANTHROPIC_MODEL env var (default: claude-haiku-4-5-20251001).
    Cost: ~$0.008 per full test run with default model.

    Override model for one-time testing:
        TEST_ANTHROPIC_MODEL=claude-sonnet-4-5 pytest tests/unit/ -k LiveClaude
    """

    def setUp(self):
        """Set up provider with test model from environment."""
        if os.getenv("ANTHROPIC_API_KEY"):
            test_model = os.getenv("TEST_ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
            self.provider = ClaudeProvider(model_name=test_model)

    @unittest.skipIf(not os.getenv("ANTHROPIC_API_KEY"), "No Anthropic API key")
    def test_live_generate_simple_prompt(self):
        """
        Verify ClaudeProvider can make a real API call and return a response.

        This test makes ONE real API call to Anthropic.
        Expected cost: ~$0.0004 with claude-haiku.
        """
        response = self.provider.generate(prompt=
            "What is 2+2? Answer with just the number.",
            temperature=0
        )

        self.assertIsNotNone(response)
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 0)
        self.assertIn("4", response)

    @unittest.skipIf(not os.getenv("ANTHROPIC_API_KEY"), "No Anthropic API key")
    def test_live_generate_with_system(self):
        """
        Verify system message is properly passed to Anthropic API.

        Anthropic expects system as a dedicated 'system' parameter,
        not injected into messages list.
        """
        response = self.provider.generate(prompt=
            "What is 5+3?",
            system="You are a helpful math tutor. Always explain your answers.",
            temperature=0
        )

        self.assertIsNotNone(response)
        self.assertIn("8", response)
        self.assertGreater(len(response), 5)

    @unittest.skipIf(not os.getenv("ANTHROPIC_API_KEY"), "No Anthropic API key")
    def test_live_generate_structured_output(self):
        """
        Verify JSON instruction works with real Anthropic API.

        Anthropic doesn't have native JSON mode, so structured_output=True
        appends JSON instruction to the system prompt.
        """
        prompt = (
            "Return a JSON object with these exact keys: "
            "'name' (set to 'test'), 'value' (set to 42), 'active' (set to true)."
        )

        response = self.provider.generate(prompt=
            prompt,
            structured_output=True,
            temperature=0
        )

        # Parse and validate
        data = parse_structured_output(response)
        self.assertIsInstance(data, dict)
        self.assertEqual(data.get("name"), "test")
        self.assertEqual(data.get("value"), 42)
        self.assertEqual(data.get("active"), True)

    @unittest.skipIf(not os.getenv("ANTHROPIC_API_KEY"), "No Anthropic API key")
    def test_live_generate_with_tools(self):
        """
        Verify tool use works with real Anthropic API.

        Anthropic has its own tool format (different from OpenAI).
        """
        registry = ToolRegistry()

        def add(a: int, b: int) -> int:
            return a + b

        registry.register(
            "add",
            add,
            description="Add two numbers",
            parameters_schema={
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"}
                },
                "required": ["a", "b"]
            }
        )

        response = self.provider.generate(prompt=
            "Use the add tool to calculate 10 + 15",
            tools=registry.to_anthropic_tools(),
            temperature=0
        )

        self.assertIsNotNone(response)
        self.assertIsInstance(response, str)

    @unittest.skipIf(not os.getenv("ANTHROPIC_API_KEY"), "No Anthropic API key")
    def test_live_multi_turn_with_messages(self):
        """
        Verify multi-turn conversation with messages parameter.
        """
        messages = [
            {"role": "user", "content": "My name is Alice."},
            {"role": "assistant", "content": "Nice to meet you, Alice!"},
            {"role": "user", "content": "What is my name?"}
        ]

        response = self.provider.generate(
            prompt=None,
            messages=messages,
            temperature=0
        )

        self.assertIn("Alice", response)


class TestLiveProviderComparison(unittest.TestCase):
    """
    Cross-provider tests comparing OpenAI and Claude behavior.

    These tests require BOTH API keys. They verify that both providers
    handle the same inputs correctly, validating provider abstraction.

    Cost: ~$0.001 per test with lightweight models.
    """

    def setUp(self):
        """Set up both providers with test models."""
        if os.getenv("OPENAI_API_KEY"):
            openai_model = os.getenv("TEST_OPENAI_MODEL", "gpt-4o-mini")
            self.openai = OpenAiProvider(model_name=openai_model)

        if os.getenv("ANTHROPIC_API_KEY"):
            claude_model = os.getenv("TEST_ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
            self.claude = ClaudeProvider(model_name=claude_model)

    @unittest.skipIf(
        not (os.getenv("OPENAI_API_KEY") and os.getenv("ANTHROPIC_API_KEY")),
        "Need both API keys"
    )
    def test_live_same_prompt_both_providers(self):
        """
        Verify both providers can handle the same simple prompt.

        This validates the unified LlmProvider interface.
        """
        prompt = "What is 2+2? Answer with just the number."

        openai_response = self.openai.generate(prompt=prompt, temperature=0)
        claude_response = self.claude.generate(prompt=prompt, temperature=0)

        # Both should return valid responses
        self.assertIsNotNone(openai_response)
        self.assertIsNotNone(claude_response)

        # Both should contain "4"
        self.assertIn("4", openai_response)
        self.assertIn("4", claude_response)

    @unittest.skipIf(
        not (os.getenv("OPENAI_API_KEY") and os.getenv("ANTHROPIC_API_KEY")),
        "Need both API keys"
    )
    def test_live_structured_output_both_providers(self):
        """
        Verify structured output parity across providers.

        OpenAI uses response_format, Claude uses JSON instruction.
        Both should produce valid JSON.
        """
        prompt = "Return a JSON object with key 'result' set to 42."

        openai_response = self.openai.generate(prompt=
            prompt,
            structured_output=True,
            temperature=0
        )
        claude_response = self.claude.generate(prompt=
            prompt,
            structured_output=True,
            temperature=0
        )

        # Both should return parseable JSON
        openai_data = parse_structured_output(openai_response)
        claude_data = parse_structured_output(claude_response)

        self.assertIsInstance(openai_data, dict)
        self.assertIsInstance(claude_data, dict)

        self.assertEqual(openai_data.get("result"), 42)
        self.assertEqual(claude_data.get("result"), 42)


if __name__ == "__main__":
    unittest.main()
