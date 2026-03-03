# Subtask 5.6 — Comprehensive Tests

## Context

Subtask 5.6 creates the full test suite for the agent framework.
It is the verification gate that confirms all prior subtask implementations
are correct before documentation (5.7) and Task 6 (workflow engine) begin.

**Prior subtask (5.5):** Delivered `AgentRegistry`, `create_agent()`,
`_is_retryable()`, `_generate_with_retry()`, and the empty response check
in `_generate_response()`.

**Next subtask (5.7):** Architecture documentation. Requires all tests
passing so the framework can be documented as stable and complete.

---

## Files to Modify / Create

| File | Action | Summary |
|------|--------|---------|
| `tests/unit/test_agents.py` | Verify / Complete | 55 tests already present; verify all pass and fix any failures |

---

## Current State (at time of plan creation)

`tests/unit/test_agents.py` was fully created during subtask 5.5 implementation.
It currently contains **55 tests** (53 mocked + 2 live) across **12 test classes**,
which exceeds the 44-test target from the parent plan.

The test class names in the implementation differ from the parent plan's names
(e.g. `TestBaseAgentInstantiation` instead of `TestBaseAgentValidation`) but
coverage is equivalent or greater across all areas.

**The real work of 5.6 is:**
1. Run the test suite and confirm all tests pass.
2. Fix any failures found.
3. Confirm the full suite (`tests/unit/`) still passes.

---

## Dependencies

- Subtasks 5.1–5.5 all marked done in `tasks.json` (verified)
- `uv sync` current — all packages installed
- `ANTHROPIC_API_KEY` set in `.env` — required for `TestLiveRestaurantInfoAgent` (mocked tests run without it)

---

## Design Decisions

### Decision 1: Exception stubs defined at module level in test file

**Choice:** `RateLimitError` and `AuthenticationError` are plain `Exception`
subclasses defined at module level in `test_agents.py`.

**Rationale:** `_is_retryable()` checks by class name (`type(exc).__name__`).
Defining the stubs in the test file means the names match the retryable set
without importing any SDK. Python sets `__name__` from the class definition
automatically.

---

### Decision 2: `time.sleep` patch path is `core.agents.base_agent.time.sleep`

**Choice:** All retry tests use `@unittest.mock.patch("core.agents.base_agent.time.sleep")`.

**Rationale:** `base_agent.py` uses `import time` (not `from time import sleep`).
The `time` name lives in the module's own namespace, so the patch must target
`core.agents.base_agent.time.sleep` — not `time.sleep` globally.

---

### Decision 3: Live tests guarded by `ANTHROPIC_API_KEY`

**Choice:** `@unittest.skipUnless(os.getenv("ANTHROPIC_API_KEY"), "ANTHROPIC_API_KEY not set")`
on `TestLiveRestaurantInfoAgent`. Uses `ClaudeProvider` with `claude-haiku-4-5-20251001`.

**Rationale:** Same pattern as Task 4.7 live tests. Cost is ~$0.001 per run.
No separate env var needed — the same key used in development is sufficient.

---

### Decision 4: Three mock provider fixtures

**Choice:** `_MockProvider`, `_MockToolProvider`, and `_FailingProvider` as
module-level fixtures.

**Rationale:**
- `_MockProvider`: single static response, records `last_call_kwargs` — used for
  non-tool tests and introspection of provider call arguments.
- `_MockToolProvider`: iterates a list of `ProviderResponse` objects via
  `generate_raw()` — required for tool calling loop tests.
- `_FailingProvider`: iterates a list of strings or `Exception` instances —
  required for retry logic tests.

---

## Test Classes and Coverage

### `TestBaseAgentInstantiation` (4 tests)
- `test_concrete_agent_instantiates` — assert `agent.name == "test-agent"`, `agent.provider is provider`, `isinstance(agent.memory, ConversationMemory)`, `agent.tools is None`
- `test_base_agent_direct_instantiation_raises` — assert `TypeError` when instantiating `BaseAgent` directly
- `test_subclass_missing_abstract_methods_raises` — assert `TypeError` when instantiating a subclass that omits `_generate_prompt` and `_process_response`
- `test_empty_name_raises_value_error` — assert `ValueError` for `name=""` and `name="   "`; message contains "cannot be empty"

### `TestInputValidation` (3 tests)
- `test_missing_schema_key_raises_before_api_call` — assert `ValueError` containing key name and agent name; assert `provider.last_call_kwargs == {}`
- `test_extra_keys_accepted_silently` — assert `run()` returns expected dict without raising when `input_data` has extra keys
- `test_empty_schema_accepts_any_input` — assert `run(input_data={})` succeeds when `INPUT_SCHEMA = {}`

### `TestRunLifecycle` (4 tests)
- `test_run_returns_expected_output` — assert `result == {"reply": "mock-response"}`
- `test_run_populates_memory_in_order` — assert `message_count == 2`, `messages[0]["role"] == "user"`, `messages[1]["role"] == "assistant"`
- `test_run_passes_context_to_generate_prompt` — assert `received_context == {"step": "onboarding"}`
- `test_run_none_context_normalized_to_empty_dict` — assert `received_context[0] == {}`

### `TestResetMemory` (1 test)
- `test_reset_memory_clears_history` — assert `message_count == 2` before; `message_count == 0` and `get_messages() == []` after `reset_memory()`

### `TestStatepersistence` (2 tests)
- `test_save_and_load_state_round_trip` — assert `messages_a == messages_b` after save on agent_a and load into fresh agent_b
- `test_load_state_unknown_session_is_noop` — assert `message_count == 1` unchanged after `load_state()` with unknown session_id

### `TestStructuredOutput` (7 tests)
- `test_response_model_passes_structured_output_true` — assert `provider.last_call_kwargs["structured_output"] is True`
- `test_no_response_model_passes_structured_output_false` — assert `provider.last_call_kwargs["structured_output"] is False`
- `test_parse_response_validates_against_response_model` — assert `result == {"reply": "hello", "confidence": 0.9}`
- `test_parse_response_invalid_json_returns_empty_dict` — assert `result == {}`
- `test_parse_response_validation_failure_returns_raw_dict` — assert `result == {"other_key": "value"}` when Pydantic validation fails
- `test_parse_response_no_response_model_returns_raw_dict` — assert `result == {"key": "value"}`
- `test_prompt_none_passed_to_provider` — assert `provider.last_call_kwargs["prompt"] is None` and `len(messages) > 0`

### `TestToolCalling` (8 tests)
- `test_register_tool_creates_registry_when_none` — assert `agent.tools is None` before; `isinstance(agent.tools, ToolRegistry)` after
- `test_register_tool_reuses_existing_registry` — assert `agent.tools is registry` after second `register_tool()` call
- `test_execute_tool_returns_result_for_valid_tool` — assert `result == "7"` for `add(3, 4)`
- `test_execute_tool_returns_error_string_for_unknown_tool` — assert `"Error" in result` and `"unknown_tool" in result`; no exception raised
- `test_execute_tool_returns_error_string_when_tool_raises` — assert `"Error" in result` and `"bad_tool" in result`; no exception raised
- `test_multi_turn_tool_loop_returns_final_text` — assert `result == {"reply": "final answer"}` and `provider.call_count == 2`
- `test_memory_contains_tool_call_and_result_after_tool_use` — assert `"tool" in roles`, tool call message present, `tool_result_msgs[0]["content"] == "42"`
- `test_exceeding_max_tool_rounds_raises_runtime_error` — assert `RuntimeError`; message contains agent name and `str(_MAX_TOOL_ROUNDS)`

### `TestBaseAgentStateManagement` (7 tests)
- `test_store_and_retrieve_round_trip` — assert `retrieve("restaurant_name") == "La Palapa"`
- `test_retrieve_missing_key_returns_none_by_default` — assert `retrieve("nonexistent_key") is None`
- `test_retrieve_missing_key_returns_explicit_default` — assert `retrieve("nonexistent_key", "fallback") == "fallback"`
- `test_clear_store_empties_store_and_leaves_memory_unchanged` — assert `retrieve("restaurant_name") is None`; assert `len(memory.get_messages()) == 1`
- `test_reset_memory_clears_memory_and_leaves_store_unchanged` — assert `retrieve("restaurant_name") == "La Palapa"`; assert `len(memory.get_messages()) == 0`
- `test_save_and_load_state_round_trip_preserves_memory_and_store` — assert `fresh.retrieve("restaurant_name") == "La Palapa"`, `fresh.retrieve("restaurant_type") == "casual"`, `len(messages) == 2`
- `test_load_state_unknown_session_is_noop` — assert `retrieve("key") == "value"` and `len(memory.get_messages()) == 0` unchanged

### `TestRestaurantInfoAgent` (6 tests)
- `test_run_returns_correct_output_structure` — assert all three keys present; `result["restaurant_name"] == "La Palapa"`, `result["restaurant_type"] == "casual"`, `result["raw_response"] == valid_response`
- `test_run_populates_memory` — assert `len(messages) == 2`, `messages[0]["content"] == "My restaurant is La Palapa."`, `messages[1]["content"] == valid_response`
- `test_missing_user_message_raises_before_api_call` — assert `ValueError` containing `"user_message"`; assert `provider.last_call_kwargs == {}`
- `test_malformed_response_handled_gracefully` — assert `result["restaurant_name"] is None`, `result["restaurant_type"] is None`, `result["raw_response"] == "Sorry, I could not understand that."`
- `test_multi_turn_accumulates_memory` — assert `len(messages) == 4`, `messages[0]["content"] == "First message."`, `messages[2]["content"] == "Second message."`
- `test_data_store_populated_after_run` — assert `retrieve("restaurant_name") == "La Palapa"` and `retrieve("restaurant_type") == "casual"`

### `TestAgentUtils` (7 tests)
- `test_is_retryable_returns_true_for_retryable_name` — assert `_is_retryable(RateLimitError()) is True`
- `test_is_retryable_returns_false_for_non_retryable_name` — assert `_is_retryable(ValueError()) is False`
- `test_create_agent_returns_correct_instance` — assert `isinstance(agent, RestaurantInfoAgent)`, `agent.name == "info-agent"`, `agent.provider is provider`
- `test_create_agent_with_non_baseagent_class_raises_type_error` — assert `TypeError` for `create_agent(str, provider=provider, name="x")`
- `test_agent_registry_register_and_get` — assert `registry.get("agent-a") is agent_a` and `registry.get("agent-b") is agent_b`
- `test_agent_registry_get_unknown_name_returns_none` — assert `registry.get("nonexistent") is None`
- `test_agent_registry_list_names_reflects_registered_agents` — assert `"alpha" in names` and `"beta" in names`

### `TestBaseAgentRetry` (4 tests, all patch `core.agents.base_agent.time.sleep`)
- `test_retry_succeeds_on_transient_error` — assert `result["restaurant_name"] == "El Cielo"`, `provider._call_count == 3`, `mock_sleep.call_count == 2`
- `test_retry_raises_after_max_retries_exhausted` — assert `RateLimitError` raised, `provider._call_count == 3`, `mock_sleep.call_count == 2`
- `test_no_retry_on_non_retryable_error` — assert `AuthenticationError` raised, `provider._call_count == 1`, `mock_sleep.assert_not_called()`
- `test_empty_response_raises_runtime_error` — assert `RuntimeError`; message contains `"retry-test"` (agent name)

### `TestLiveRestaurantInfoAgent` (2 tests, `@skipUnless ANTHROPIC_API_KEY`)
- `test_live_extracts_restaurant_info` — assert `result["restaurant_name"] is not None` and `result["restaurant_type"] is not None`
- `test_live_multi_turn_extracts_across_turns` — assert `len(messages) == 4`, `messages[0]["content"] == "My restaurant is called El Fogón."`, `result2["restaurant_type"] is not None`

---

## Test Count Summary

| Class | Mocked | Live |
|-------|--------|------|
| TestBaseAgentInstantiation | 4 | 0 |
| TestInputValidation | 3 | 0 |
| TestRunLifecycle | 4 | 0 |
| TestResetMemory | 1 | 0 |
| TestStatepersistence | 2 | 0 |
| TestStructuredOutput | 7 | 0 |
| TestToolCalling | 8 | 0 |
| TestBaseAgentStateManagement | 7 | 0 |
| TestRestaurantInfoAgent | 6 | 0 |
| TestAgentUtils | 7 | 0 |
| TestBaseAgentRetry | 4 | 0 |
| TestLiveRestaurantInfoAgent | 0 | 2 |
| **Total** | **53** | **2** |

---

## Out of Scope

- Retry logic tests for the tool calling loop (`provider.generate_raw()`)
- Tests for `AgentRegistry.clear()`
- OpenAI live tests
- Any changes to `base_agent.py`, `simple_agent.py`, or `utils.py`
- Agent serialization beyond `save_state`/`load_state`

---

## Risks and Open Questions

1. **Tests have not been run yet.** The file exists but no pytest run has been
   confirmed. The primary risk is an import error or a subtle fixture mismatch
   causing failures that block 5.7.

2. **`_generate_with_retry()` implicit None return for `max_retries=0`.**
   The loop body raises on the final attempt, so `None` can only be returned
   if `max_retries=0` (empty range). The call site always uses the default (3),
   so this is not a test risk — but the return type annotation `-> str` is
   technically imprecise for that edge case.

3. **`_MockToolProvider._do_generate` returns `""`** — only `generate_raw()` is
   called in tool tests, so this is never invoked. No test failure risk.

---

## Verification Commands

```bash
# Run only the agent test file
python -m pytest tests/unit/test_agents.py -v

# Run with live tests (requires ANTHROPIC_API_KEY in .env)
ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY .env | cut -d= -f2) \
  python -m pytest tests/unit/test_agents.py -v

# Run full suite to confirm no regressions
python -m pytest tests/unit/ -v
```

---

## Deliverable Checklist

### `tests/unit/test_agents.py`
- [x] File exists at `tests/unit/test_agents.py`
- [x] `RateLimitError` and `AuthenticationError` defined at module level
- [x] `_MockProvider`, `_MockToolProvider`, `_FailingProvider` fixtures defined
- [x] `_ConcreteAgent`, `_TypedAgent`, `_ToolAgent` stub agents defined
- [x] `TestBaseAgentInstantiation` — 4 tests
- [x] `TestInputValidation` — 3 tests
- [x] `TestRunLifecycle` — 4 tests
- [x] `TestResetMemory` — 1 test
- [x] `TestStatepersistence` — 2 tests
- [x] `TestStructuredOutput` — 7 tests
- [x] `TestToolCalling` — 8 tests
- [x] `TestBaseAgentStateManagement` — 7 tests
- [x] `TestRestaurantInfoAgent` — 6 tests
- [x] `TestAgentUtils` — 7 tests
- [x] `TestBaseAgentRetry` — 4 tests (all patch `core.agents.base_agent.time.sleep`)
- [x] `TestLiveRestaurantInfoAgent` — 2 tests (guarded by `ANTHROPIC_API_KEY`)
- [x] All tests pass: `python -m pytest tests/unit/test_agents.py -v` — 55 passed
- [x] Full suite passes: `python -m pytest tests/unit/ -v` — 462 passed
