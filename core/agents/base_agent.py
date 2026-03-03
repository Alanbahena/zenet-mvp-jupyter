"""
BaseAgent -- abstract base class for all Zenet agents.

Every notebook agent (WelcomeAgent, ClassificationAgent, etc.) extends BaseAgent
and implements two abstract methods:
    - _generate_prompt(input_data, context) -> tuple[str, str]
    - _process_response(response) -> dict

The run() method orchestrates the full lifecycle:
    validate input -> build prompts -> generate response -> parse output

Tool calling (5.2), state and memory management (5.3), and retry logic (5.5) are added
in subsequent subtasks without modifying run().
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic import BaseModel

from core.ai.memory import ConversationMemory
from core.ai.providers import LlmProvider, ProviderResponse, ToolRegistry
from core.ai.utils import parse_structured_output
from core.storage.persistence import DataLake
from core.agents.utils import _is_retryable


@dataclass
class BaseAgent(ABC):
    """
    Abstract base class for all Zenet notebook agents.

    Subclasses must implement:
        - _generate_prompt(input_data, context) -> tuple[str, str]
        - _process_response(response) -> dict[str, Any]

    Class-level schema attributes (ClassVar -- not dataclass fields):
        INPUT_SCHEMA:   dict[str, str]          -- keys the agent requires in input_data
        OUTPUT_SCHEMA:  dict[str, str]          -- keys the agent returns (Task 6 contract)
        RESPONSE_MODEL: type[BaseModel] | None  -- Pydantic model for LLM JSON response

    Instance fields:
        name:        str                -- identifier used in error messages and storage keys
        provider:    LlmProvider        -- LLM provider (OpenAI, Claude)
        memory:      ConversationMemory -- conversation history (injected or fresh)
        tools:       ToolRegistry | None -- tool registry for function calling (5.2)
        _data_store: dict[str, Any]     -- structured business data extracted during conversation (5.3)
    """

    INPUT_SCHEMA:    ClassVar[dict[str, str]]         = {}
    OUTPUT_SCHEMA:   ClassVar[dict[str, str]]         = {}
    RESPONSE_MODEL:  ClassVar[type[BaseModel] | None] = None
    _MAX_TOOL_ROUNDS: ClassVar[int]                   = 10

    name:        str
    provider:    LlmProvider
    memory:      ConversationMemory = field(default_factory=ConversationMemory)
    tools:       ToolRegistry | None = None
    _data_store: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        """Validate fields after dataclass initialization."""
        if not self.name.strip():
            raise ValueError("Agent name cannot be empty.")

    # ------------------------------------------------------------------
    # Abstract methods — must be implemented by every concrete agent
    # ------------------------------------------------------------------

    @abstractmethod
    def _generate_prompt(
        self,
        input_data: dict[str, Any],
        context: dict[str, Any],
    ) -> tuple[str, str]:
        """
        Build system and user prompts from input data and workflow context.

        Args:
            input_data: Validated input dict. All INPUT_SCHEMA keys are guaranteed present.
            context:    Workflow context passed from the previous pipeline step.
                        May be empty ({}). Structure is defined by Task 6, not BaseAgent.

        Returns:
            (system_prompt, user_prompt) -- always a 2-tuple of non-empty strings.
            System and user content must be separated; never merge them into one string.

        Note:
            When RESPONSE_MODEL is defined, _generate_response() automatically enables
            structured output mode. The system prompt does not need to manually instruct
            the LLM to return JSON -- that is handled at the provider level.
        """

    @abstractmethod
    def _process_response(self, response: str) -> dict[str, Any]:
        """
        Parse the raw LLM response string into a structured output dict.

        Args:
            response: Raw LLM response string as returned by the provider.

        Returns:
            Dict conforming to OUTPUT_SCHEMA. Keys declared in OUTPUT_SCHEMA may be
            None if the information was not present -- BaseAgent does not validate
            the output dict against OUTPUT_SCHEMA.

        Tip:
            Use self._parse_response(response) to handle JSON parsing and Pydantic
            validation against RESPONSE_MODEL in one call, then build the output dict
            from the validated result.
        """

    # ------------------------------------------------------------------
    # Lifecycle methods
    # ------------------------------------------------------------------

    def run(
        self,
        *,
        input_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute the full agent lifecycle.

        Steps:
            1. Validate input_data against INPUT_SCHEMA
            2. Build (system_prompt, user_prompt) via _generate_prompt()
            3. Add user_prompt to conversation memory
            4. Generate LLM response via _generate_response()
               (structured output enabled automatically if RESPONSE_MODEL is defined)
            5. Add response to conversation memory
            6. Parse and return structured output via _process_response()

        Args:
            input_data: Input dict; must satisfy INPUT_SCHEMA. Extra keys are accepted.
            context:    Optional workflow context from previous pipeline steps.
                        Passed through to _generate_prompt() unchanged.

        Returns:
            Dict as returned by _process_response(). Keys depend on OUTPUT_SCHEMA.

        Raises:
            ValueError: If input_data is missing required INPUT_SCHEMA keys.
        """
        self._validate_input(input_data)
        system_prompt, user_prompt = self._generate_prompt(input_data, context or {})
        self.memory.add_user(user_prompt)
        response = self._generate_response(system_prompt)
        self.memory.add_assistant(response)
        return self._process_response(response)

    def reset_memory(self) -> None:
        """
        Clear conversation history.

        Does not affect the agent data store. Use clear_store() to reset stored data.
        Use this to start a fresh conversation without creating a new agent instance.
        """
        self.memory.clear()

    def store(self, key: str, value: Any) -> None:
        """
        Store a value in the agent's data store.

        The data store holds structured business data extracted during the conversation
        (e.g. restaurant name, operator concerns). It is separate from conversation memory
        and is persisted by save_state() alongside the message history.

        Args:
            key:   String key. Overwrites existing value if key already exists.
            value: Any Python value. No type constraint -- store what the agent extracts.
        """
        self._data_store[key] = value

    def retrieve(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value from the agent's data store.

        Args:
            key:     Key to look up.
            default: Value returned when key is not present. Defaults to None.

        Returns:
            The stored value, or default if key does not exist.
        """
        return self._data_store.get(key, default)

    def clear_store(self) -> None:
        """
        Clear all data in the agent's data store.

        Does not affect conversation memory. Use reset_memory() to clear message history.
        Use this to reset collected business data without discarding the conversation.
        """
        self._data_store.clear()

    def save_state(self, data_lake: DataLake, *, session_id: str) -> None:
        """
        Persist conversation memory and data store to DataLake.

        Both are saved together under the same session_id. Call load_state() with
        the same session_id and DataLake instance to restore both.

        Args:
            data_lake:  DataLake instance for storage.
            session_id: Unique session identifier. Must be unique per agent instance
                        to avoid key collisions in multi-agent workflows.
        """
        data_lake.save_entity("agent_state", session_id, {
            "agent_name": self.name,
            "memory": self.memory.to_dict(),
            "data_store": self._data_store,
        })

    def load_state(self, data_lake: DataLake, *, session_id: str) -> None:
        """
        Restore conversation memory and data store from DataLake.

        No-op if session_id does not exist in storage -- agent state is unchanged.
        Memory and data store are always restored together to maintain consistency.

        Args:
            data_lake:  DataLake instance for storage.
            session_id: Session identifier used when save_state() was called.
        """
        state = data_lake.load_entity("agent_state", session_id)
        if state:
            self.memory = ConversationMemory.from_dict(state["memory"])
            self._data_store = state.get("data_store", {})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_input(self, input_data: dict[str, Any]) -> None:
        """
        Raise ValueError if any INPUT_SCHEMA keys are missing from input_data.

        Called at the start of run() before any prompt construction or API call.
        Extra keys in input_data beyond INPUT_SCHEMA are silently accepted.
        An empty INPUT_SCHEMA ({}) means no validation -- all inputs accepted.
        """
        missing = [k for k in self.INPUT_SCHEMA if k not in input_data]
        if missing:
            raise ValueError(
                f"[{self.name}] Missing required input keys: {missing}. "
                f"Expected: {list(self.INPUT_SCHEMA.keys())}"
            )

    def _parse_response(self, response: str) -> dict[str, Any]:
        """
        Parse the raw LLM response string and validate against RESPONSE_MODEL.

        Convenience helper for use inside _process_response(). Handles:
            1. JSON parsing via parse_structured_output()
            2. Pydantic model validation when RESPONSE_MODEL is defined
            3. Graceful fallback to raw parsed dict if Pydantic validation fails

        Args:
            response: Raw LLM response string.

        Returns:
            Validated and model-dumped dict if RESPONSE_MODEL is defined and valid.
            Raw parsed dict if RESPONSE_MODEL is None or validation fails.
            Empty dict {} if JSON parsing fails entirely.
        """
        try:
            data = parse_structured_output(response)
        except (ValueError, Exception):
            return {}
        if self.RESPONSE_MODEL is not None and data:
            try:
                validated = self.RESPONSE_MODEL.model_validate(data)
                return validated.model_dump()
            except Exception:
                return data
        return data

    def _generate_response(self, system_prompt: str) -> str:
        """
        Generate LLM response using current conversation memory.

        When self.tools is None: single-turn call via _generate_with_retry(), which
        wraps provider.generate() with exponential backoff on transient API errors.
        Raises RuntimeError if the provider returns an empty string.

        When self.tools is set: multi-turn tool calling loop via provider.generate_raw().
            Per round:
                1. Call generate_raw() with current memory and tools.
                2. If tool calls returned: execute each, add results to memory, repeat.
                3. If text returned: return it (loop exits).
            After _MAX_TOOL_ROUNDS without a final text response: raise RuntimeError.
            The tool calling loop does not retry individual generate_raw() calls.

        Automatically enables structured output mode when RESPONSE_MODEL is defined,
        consistent across both paths.

        Note: prompt=None is critical. The user message is already in self.memory
        (added by run()). Passing prompt alongside messages would duplicate it.
        """
        if self.tools is None:
            result = self._generate_with_retry(
                prompt=None,
                system=system_prompt,
                messages=self.memory.get_messages(),
                structured_output=self.RESPONSE_MODEL is not None,
            )
            if not result:
                raise RuntimeError(
                    f"[{self.name}] LLM returned an empty response."
                )
            return result

        for _ in range(self._MAX_TOOL_ROUNDS):
            raw: ProviderResponse = self.provider.generate_raw(
                prompt=None,
                system=system_prompt,
                messages=self.memory.get_messages(),
                tools=self.tools,
                structured_output=self.RESPONSE_MODEL is not None,
            )
            if raw.has_tool_calls:
                self.memory.add_tool_call(raw.tool_calls)
                for call in raw.tool_calls:
                    result = self._execute_tool(call)
                    self.memory.add_tool_result(call["id"], result)
                continue
            return raw.text or ""

        raise RuntimeError(
            f"[{self.name}] Exceeded maximum tool rounds ({self._MAX_TOOL_ROUNDS}). "
            "The LLM did not return a final text response within the allowed rounds."
        )

    def _generate_with_retry(
        self,
        *,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> str:
        """
        Generate LLM response with exponential backoff on transient API errors.

        Retries on: RateLimitError, APITimeoutError, APIConnectionError,
                    ServiceUnavailableError, InternalServerError, Timeout, ConnectionError.
        Does not retry on: authentication errors, invalid request errors.

        Args:
            max_retries: Maximum number of attempts (default 3). On the final attempt,
                         the exception is re-raised regardless of type.
            **kwargs:    Forwarded to provider.generate(). Must match its signature:
                         prompt, system, messages, structured_output, tools, etc.

        Returns:
            LLM response string. May be "" if the provider returns no content;
            _generate_response() is responsible for raising on empty.

        Raises:
            Exception: Re-raised from the provider when all retries are exhausted,
                       or immediately if the error is not retryable.
        """
        delay = 1.0
        for attempt in range(max_retries):
            try:
                return self.provider.generate(**kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                if _is_retryable(e):
                    time.sleep(delay)
                    delay *= 2
                else:
                    raise

    def _execute_tool(self, tool_call: dict[str, Any]) -> str:
        """
        Execute a single tool call and return the result as a string.

        Never raises. Tool errors are returned as descriptive strings so the LLM
        can read them, explain the issue to the user, or try a different approach.

        Args:
            tool_call: Normalized tool call dict from ProviderResponse.tool_calls.
                       Format: {"id": "...", "function": {"name": "...", "arguments": "..."}}
                       arguments is a JSON string; parsed to dict before execution.

        Returns:
            str(result) on success.
            "Error: tool '<name>' not registered." for unknown tools.
            "Error executing '<name>': <exception>" if the tool function raises.
        """
        function = tool_call.get("function", {})
        name = function.get("name", "")
        args = function.get("arguments", {})

        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}

        try:
            result = self.tools.execute(name, args)
            return str(result)
        except ValueError:
            return f"Error: tool '{name}' not registered."
        except Exception as e:
            return f"Error executing '{name}': {e}"

    def register_tool(
        self,
        name: str,
        func: Callable[..., Any],
        *,
        description: str,
        parameters_schema: dict[str, Any] | None = None,
    ) -> None:
        """
        Register a tool with the agent.

        Auto-creates a ToolRegistry if the agent was initialized without one
        (tools=None). Subsequent calls reuse the same registry.

        Args:
            name:              Tool name (must be unique; duplicates overwrite).
            func:              Callable to execute when the LLM requests this tool.
            description:       Human/LLM-readable description of what the tool does.
            parameters_schema: JSON schema dict for the tool's parameters.
                               If None, defaults to {"type": "object", "properties": {}}.
        """
        if self.tools is None:
            self.tools = ToolRegistry()
        self.tools.register(
            name, func, description=description, parameters_schema=parameters_schema
        )
