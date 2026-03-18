# Subtask 9.5 — Tests (`tests/unit/test_configuration_agent.py`)

## Context

Creates the test file for `ConfigurationAgent`, `ConsistencyCheckAgent`, and the
confirm/save logic in `gradio_app/sections/configuracion.py`. All mocked tests run
offline; live tests are guarded by `ANTHROPIC_API_KEY`.

**Prior (9.4):** Both agents exported from `core.agents` and `core` — test file imports
via package root.

**Next (9.6):** Documentation and task closure — requires full test suite green first.

---

## File to Create

| File | Action | Summary |
|------|--------|---------|
| `tests/unit/test_configuration_agent.py` | Create | 16 mocked + 3 live tests |

---

## Dependencies

- 9.1–9.4 done ✓
- `ConfigurationAgent` importable from `core.agents` ✓
- `ConsistencyCheckAgent` importable from `core.agents` ✓
- `_make_confirm_fn`, `_save_step` importable from `gradio_app.sections.configuracion`
- `ANTHROPIC_API_KEY` in `.env` (live tests only)
- No new packages — `unittest`, `json`, `os`, `tempfile` are stdlib

---

## Pattern Reference

Follow `tests/unit/test_classification_agent.py` exactly for:
- `_MockProvider` structure (subclass `LlmProvider`, override `_do_generate`, capture `last_system`)
- `_make_data_lake()` helper
- `@unittest.skipUnless(os.getenv("ANTHROPIC_API_KEY"), "requires ANTHROPIC_API_KEY")` guard
- Class grouping: one `unittest.TestCase` subclass per logical group

---

## Response Schema Helpers

Two JSON-builder helpers — one per agent response model:

```python
def _config_response(
    reply: str = "Ok.",
    entities: list | None = None,
    step_complete: bool | None = None,
) -> str:
    return json.dumps({"reply": reply, "entities": entities, "step_complete": step_complete})


def _check_response(
    issues: list[str] | None = None,
    suggestions: list[str] | None = None,
    looks_good: bool = True,
) -> str:
    return json.dumps({
        "issues": issues or [],
        "suggestions": suggestions or [],
        "looks_good": looks_good,
    })
```

---

## Mock Provider

```python
class _MockProvider(LlmProvider):
    def __init__(self, response: str | None = None) -> None:
        super().__init__(model_name="mock")
        self.response = response or _config_response()
        self.last_system: str = ""

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
        self.last_system = system or ""
        return self.response
```

---

## Test Classes and Individual Tests

### `TestConfigurationAgent` — 10 mocked tests

```python
def _make_agent(self, response=None):
    provider = _MockProvider(response=response)
    agent = create_agent(ConfigurationAgent, provider=provider, name="configuration_agent")
    return agent, provider
```

| Test | Setup | Assertion |
|---|---|---|
| `test_agent_instantiates_via_factory` | `create_agent(ConfigurationAgent, ...)` | `assertIsInstance(agent, ConfigurationAgent)` |
| `test_response_model_is_set` | — | `assertIsNotNone(ConfigurationAgent.RESPONSE_MODEL)` |
| `test_run_returns_reply` | default mock response | `assertTrue(result["reply"])` |
| `test_run_stores_entities_in_data_store` | response with `entities=[{"name":"Comidas","description":"Platillos del día"}]`, context `current_step="categories"` | `assertEqual(agent.retrieve("categories"), [...])` |
| `test_run_does_not_overwrite_existing_entities` | first turn: entities list; second turn: `entities=None` | `assertEqual(agent.retrieve("categories"), first_turn_list)` |
| `test_context_injects_restaurant_type` | context `{"restaurant_type": "Casual", ...}` | `assertIn("Casual", provider.last_system)` |
| `test_context_injects_classification_level` | context `{"standardization_level": 3, ...}` | `assertIn("3", provider.last_system)` |
| `test_draft_injected_in_prompt` | run two turns; first sets entities | `assertIn("categories", provider.last_system)` on second turn |
| `test_save_load_state_preserves_all_steps` | run with entities for each of the four step keys; `save_state`; fresh agent `load_state` | all four lists present in `agent2._data_store` |
| `test_missing_user_message_raises` | `run(input_data={})` | `assertRaises(ValueError)` |

**Note on `test_save_load_state_preserves_all_steps`:** Run the agent four times, each with
a different `current_step` key in context and a mock response that returns a non-None
`entities` list. Then `save_state`, load into a fresh agent, and assert all four keys
(`"categories"`, `"families"`, `"recipe_units"`, `"inventory_units"`) are present and
non-empty in `_data_store`.

---

### `TestConsistencyCheckAgent` — 3 mocked tests

| Test | Input shape | Mock response | Assertion |
|---|---|---|---|
| `test_consistency_check_returns_issues` | per-step: `{"step":"recipe_units","entities":[],"restaurant_type":"Casual"}` | `_check_response(issues=["Falta unidad de volumen"], looks_good=False)` | `assertFalse(result["looks_good"])`, `assertTrue(result["issues"])` |
| `test_consistency_check_no_issues_looks_good` | per-step: well-configured list | `_check_response(looks_good=True)` | `assertTrue(result["looks_good"])`, `assertEqual(result["issues"], [])` |
| `test_consistency_check_cross_entity` | final shape: all four lists; recipe_units has "taza" but inventory_units empty | `_check_response(issues=["Sin unidad de volumen estándar"], looks_good=False)` | `assertFalse(result["looks_good"])`, issue string present in `result["issues"][0]` |

---

### `TestConfirmFn` — 3 mocked tests

All three tests use `issues_ack=True` to bypass the internal `ConsistencyCheckAgent`
LLM call — this is the correct offline approach since `_make_confirm_fn` creates its
own `ClaudeProvider()` internally.

```python
_SAMPLE_CATS = [{"name": "Comidas", "description": "Platillos del día"}]
_SAMPLE_FAMS = [{"name": "Lácteos", "description": "Productos lácteos"}]
_SAMPLE_RU   = [{"name": "gramo", "symbol": "g", "description": "Unidad de peso"}]
_SAMPLE_IU   = [{"name": "kilogramo", "symbol": "kg", "is_standard": True, "description": "Unidad base"}]
```

| Test | Call | Assertion |
|---|---|---|
| `test_confirm_fn_persists_entities` | `confirm_fn(0, _SAMPLE_CATS, [], [], [], True, "sess")` | `data_lake.list_ids("category_recipe")` non-empty; loaded entity name == "Comidas" |
| `test_confirm_fn_empty_session_returns_error` | `confirm_fn(0, _SAMPLE_CATS, [], [], [], True, "")` | returned status contains "Sesión"; `data_lake.list_ids("category_recipe")` empty |
| `test_id_assignment_sequential` | `_save_step(dl, "categories", [{"name":"A","description":None}, {"name":"B","description":None}])` | `dl.load_entity("category_recipe", 1)["name"] == "A"`, `dl.load_entity("category_recipe", 2)["name"] == "B"` |

---

### `TestConfigurationAgentLive` — 3 live tests

Decorated: `@unittest.skipUnless(os.getenv("ANTHROPIC_API_KEY"), "requires ANTHROPIC_API_KEY")`

`setUpClass`: instantiate `ClaudeProvider` once and store as `cls.provider`.

| Test | Run | Assertion |
|---|---|---|
| `test_live_responds_in_spanish` | `agent.run({"user_message": "Hola, ¿cómo funciona esta sección?"})` with context `current_step="categories"` | reply contains a Spanish word from `["categoría","receta","restaurante","zenet","nivel"]`; `"{"` not in reply |
| `test_live_proposes_categories_for_casual` | `agent.run({"user_message": "Sí, continúa"})` with context `restaurant_type="Casual"`, `current_step="categories"` | `result["entities"]` is not None; `len(result["entities"]) >= 1` |
| `test_live_consistency_check_flags_missing_unit` | `ConsistencyCheckAgent.run({"step":"recipe_units","entities":[],"restaurant_type":"Casual"})` using real provider | `result["looks_good"] == False`; `len(result["issues"]) >= 1` |

---

## Running the Tests

```bash
# Mocked only (no API key needed)
uv run python -m pytest tests/unit/test_configuration_agent.py -v -k "not Live"

# Full suite including live tests (requires ANTHROPIC_API_KEY)
uv run python -m pytest tests/unit/test_configuration_agent.py -v

# Full unit suite
uv run python -m pytest tests/unit/ -v
```

---

## Out of Scope

- Changes to any agent implementation file
- Changes to `configuracion.py`
- Changes to `__init__.py` files
- Tests for `_load_configuration_context` or `_init_section` (not in parent plan test list)
- Documentation (9.6)

---

## Risks and Open Questions

### [OPEN] — `_load_configuration_context` and `_init_section` have no dedicated tests
**Source:** Validation of subtask 9.3, confirmed in 9.5 planning
**Problem:** Both functions contain branching logic (Level 1 fallback, resume index
detection) that is not covered by any test in the parent plan's test list.
**Impact:** Regressions in resume behavior or level-fallback logic won't be caught by
the test suite.
**Suggested action:** Add 2 mocked tests in this file if time permits — they require
only a `_make_data_lake()` and a `save_entity` call, no LLM mock needed. Otherwise
defer to Task 10 when these functions are exercised more broadly.

---

## Deliverable Checklist

### `tests/unit/test_configuration_agent.py`
- [ ] `_MockProvider` defined, subclasses `LlmProvider`, overrides `_do_generate`
- [ ] `_config_response()` helper builds `ConfigurationAgent` JSON response
- [ ] `_check_response()` helper builds `ConsistencyCheckAgent` JSON response
- [ ] `TestConfigurationAgent` — 10 mocked tests all pass offline
- [ ] `TestConsistencyCheckAgent` — 3 mocked tests all pass offline
- [ ] `TestConfirmFn` — 3 mocked tests all pass offline; all use `issues_ack=True`
- [ ] `TestConfigurationAgentLive` — 3 live tests guarded by `ANTHROPIC_API_KEY`
- [ ] Full mocked suite passes: `uv run python -m pytest tests/unit/test_configuration_agent.py -v -k "not Live"`
- [ ] Full unit suite passes: `uv run python -m pytest tests/unit/ -v`
