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
| `tests/unit/test_agents.py` | Create | 42 mocked tests + 2 live tests across 8 test classes |

---

## Current State (at time of plan creation)

`tests/unit/test_agents.py` was partially created during subtask 5.5 implementation.
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
- `test_concrete_agent_instantiates` — correct fields set on construction
- `test_base_agent_direct_instantiation_raises` — `TypeError` for abstract class
- `test_subclass_missing_abstract_methods_raises` — `TypeError` for incomplete subclass
- `test_empty_name_raises_value_error` — `__post_init__` rejects empty/whitespace name

### `TestInputValidation` (3 tests)
- `test_missing_schema_key_raises_before_api_call` — `ValueError` before any API call; error contains agent name and key
- `test_extra_keys_accepted_silently` — extra keys in `input_data` do not raise
- `test_empty_schema_accepts_any_input` — `INPUT_SCHEMA = {}` means no validation

### `TestRunLifecycle` (4 tests)
- `test_run_returns_expected_output` — `run()` returns `_process_response()` dict
- `test_run_populates_memory_in_order` — user then assistant message after `run()`
- `test_run_passes_context_to_generate_prompt` — context dict passed through unchanged
- `test_run_none_context_normalized_to_empty_dict` — `context=None` becomes `{}`

### `TestResetMemory` (1 test)
- `test_reset_memory_clears_history` — message count drops to 0 after `reset_memory()`

### `TestStatePersistence` (2 tests)
- `test_save_and_load_state_round_trip` — memory preserved across fresh agent instance
- `test_load_state_unknown_session_is_noop` — missing session_id leaves state unchanged

### `TestStructuredOutput` (7 tests)
- `test_response_model_passes_structured_output_true`
- `test_no_response_model_passes_structured_output_false`
- `test_parse_response_validates_against_response_model`
- `test_parse_response_invalid_json_returns_empty_dict`
- `test_parse_response_validation_failure_returns_raw_dict`
- `test_parse_response_no_response_model_returns_raw_dict`
- `test_prompt_none_passed_to_provider` — `prompt=None` prevents message duplication

### `TestToolCalling` (8 tests)
- `test_register_tool_creates_registry_when_none`
- `test_register_tool_reuses_existing_registry`
- `test_execute_tool_returns_result_for_valid_tool`
- `test_execute_tool_returns_error_string_for_unknown_tool`
- `test_execute_tool_returns_error_string_when_tool_raises`
- `test_multi_turn_tool_loop_returns_final_text`
- `test_memory_contains_tool_call_and_result_after_tool_use`
- `test_exceeding_max_tool_rounds_raises_runtime_error`

### `TestBaseAgentStateManagement` (7 tests)
- `test_store_and_retrieve_round_trip`
- `test_retrieve_missing_key_returns_none_by_default`
- `test_retrieve_missing_key_returns_explicit_default`
- `test_clear_store_empties_store_and_leaves_memory_unchanged`
- `test_reset_memory_clears_memory_and_leaves_store_unchanged`
- `test_save_and_load_state_round_trip_preserves_memory_and_store`
- `test_load_state_unknown_session_is_noop`

### `TestRestaurantInfoAgent` (6 tests)
- `test_run_returns_correct_output_structure`
- `test_run_populates_memory`
- `test_missing_user_message_raises_before_api_call`
- `test_malformed_response_handled_gracefully`
- `test_multi_turn_accumulates_memory`
- `test_data_store_populated_after_run`

### `TestAgentUtils` (7 tests)
- `test_is_retryable_returns_true_for_retryable_name`
- `test_is_retryable_returns_false_for_non_retryable_name`
- `test_create_agent_returns_correct_instance`
- `test_create_agent_with_non_baseagent_class_raises_type_error`
- `test_agent_registry_register_and_get`
- `test_agent_registry_get_unknown_name_returns_none`
- `test_agent_registry_list_names_reflects_registered_agents`

### `TestBaseAgentRetry` (4 tests, all patch `core.agents.base_agent.time.sleep`)
- `test_retry_succeeds_on_transient_error` — fails twice then succeeds; `sleep` called 2 times
- `test_retry_raises_after_max_retries_exhausted` — always fails; `sleep` called 2 times
- `test_no_retry_on_non_retryable_error` — raises immediately; `sleep` never called
- `test_empty_response_raises_runtime_error` — `RuntimeError` contains agent name

### `TestLiveRestaurantInfoAgent` (2 tests, `@skipUnless ANTHROPIC_API_KEY`)
- `test_live_extracts_restaurant_info` — real Claude call returns non-None name and type
- `test_live_multi_turn_extracts_across_turns` — two turns accumulate 4 messages; type extracted in turn 2

---

## Test Count Summary

| Class | Mocked | Live |
|-------|--------|------|
| TestBaseAgentInstantiation | 4 | 0 |
| TestInputValidation | 3 | 0 |
| TestRunLifecycle | 4 | 0 |
| TestResetMemory | 1 | 0 |
| TestStatePersistence | 2 | 0 |
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
- [ ] File exists at `tests/unit/test_agents.py`
- [ ] `RateLimitError` and `AuthenticationError` defined at module level
- [ ] `_MockProvider`, `_MockToolProvider`, `_FailingProvider` fixtures defined
- [ ] `_ConcreteAgent`, `_TypedAgent`, `_ToolAgent` stub agents defined
- [ ] `TestBaseAgentInstantiation` — 4 tests
- [ ] `TestInputValidation` — 3 tests
- [ ] `TestRunLifecycle` — 4 tests
- [ ] `TestResetMemory` — 1 test
- [ ] `TestStatePersistence` — 2 tests
- [ ] `TestStructuredOutput` — 7 tests
- [ ] `TestToolCalling` — 8 tests
- [ ] `TestBaseAgentStateManagement` — 7 tests
- [ ] `TestRestaurantInfoAgent` — 6 tests
- [ ] `TestAgentUtils` — 7 tests
- [ ] `TestBaseAgentRetry` — 4 tests (all patch `core.agents.base_agent.time.sleep`)
- [ ] `TestLiveRestaurantInfoAgent` — 2 tests (guarded by `ANTHROPIC_API_KEY`)
- [ ] All tests pass: `python -m pytest tests/unit/test_agents.py -v`
- [ ] Full suite passes: `python -m pytest tests/unit/ -v`
