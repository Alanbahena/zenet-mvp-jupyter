"""
BaseAgent -- abstract base class for all Zenet agents.

Every notebook agent (WelcomeAgent, ClassificationAgent, etc.) extends BaseAgent
and implements two abstract methods:
    - _generate_prompt(input_data, context) -> tuple[str, str]
    - _process_response(response) -> dict

The run() method orchestrates the full lifecycle:
    validate input -> build prompts -> generate response -> parse output

Tool calling (5.2), data store (5.3), and retry logic (5.5) are added
in subsequent subtasks without modifying run().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic import BaseModel

from core.ai.memory import ConversationMemory
from core.ai.providers import LlmProvider, ToolRegistry
from core.ai.utils import parse_structured_output
from core.storage.persistence import DataLake


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
        name:     str                -- identifier used in error messages and storage keys
        provider: LlmProvider        -- LLM provider (OpenAI, Claude)
        memory:   ConversationMemory -- conversation history (injected or fresh)
        tools:    ToolRegistry | None -- tool registry for function calling (5.2)
    """

    INPUT_SCHEMA:   ClassVar[dict[str, str]]         = {}
    OUTPUT_SCHEMA:  ClassVar[dict[str, str]]         = {}
    RESPONSE_MODEL: ClassVar[type[BaseModel] | None] = None

    name:     str
    provider: LlmProvider
    memory:   ConversationMemory = field(default_factory=ConversationMemory)
    tools:    ToolRegistry | None = None

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

        Does not affect the agent data store (subtask 5.3).
        Use this to start a fresh conversation without creating a new agent instance,
        for example when moving between pipeline stages with the same agent.
        """
        self.memory.clear()

    def save_state(self, data_lake: DataLake, *, session_id: str) -> None:
        """
        Persist conversation memory to DataLake.

        Subtask 5.3 extends this to also persist the agent data store.

        Args:
            data_lake:  DataLake instance for storage.
            session_id: Unique session identifier. Used as the storage key.
                        Must be unique per agent instance to avoid key collisions.
        """
        data_lake.save_entity("agent_state", session_id, {
            "agent_name": self.name,
            "memory": self.memory.to_dict(),
        })

    def load_state(self, data_lake: DataLake, *, session_id: str) -> None:
        """
        Restore conversation memory from DataLake.

        No-op if session_id does not exist in storage -- agent state is unchanged.
        Subtask 5.3 extends this to also restore the agent data store.

        Args:
            data_lake:  DataLake instance for storage.
            session_id: Session identifier used when save_state() was called.
        """
        state = data_lake.load_entity("agent_state", session_id)
        if state:
            self.memory = ConversationMemory.from_dict(state["memory"])

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

        Automatically enables structured output mode when RESPONSE_MODEL is defined:
            - OpenAI: response_format={"type": "json_object"} (API-level guarantee)
            - Claude: JSON instruction injected into system prompt

        Subtask 5.2 replaces this method with the tool calling loop.
        In 5.1: single-turn, no tool use.
        In 5.2: multi-turn loop that executes tool calls until a final text response.

        Args:
            system_prompt: System-level instructions for the LLM.
                           User content is already in self.memory (added by run()).

        Returns:
            Raw LLM response string.

        Note:
            prompt=None is critical here. By the time this method is called, run() has
            already added the user message to self.memory. Passing prompt=user_prompt
            alongside messages would duplicate the user message in the conversation.
        """
        return self.provider.generate(
            prompt=None,
            system=system_prompt,
            messages=self.memory.get_messages(),
            structured_output=self.RESPONSE_MODEL is not None,
        )
