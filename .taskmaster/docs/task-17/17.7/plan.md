# Subtask 17.7 — Tests for Restaurant Description Flow

## Goal

Add mocked tests covering the restaurant description flow across ClassificationAgent,
ConfigurationAgent, ConsistencyCheckAgent, and the confirm persistence path, completing
Task 17's test coverage.

- **Prior (17.6):** All description field changes are in place across all agents and
  the confirm/load flow.
- **Following:** Task 17 fully closed; Task 10 (Alineamiento) can begin with the
  enriched context available.

---

## What changes

| File | Action | Summary |
|------|--------|---------|
| `tests/unit/test_classification_agent.py` | Modify | Add tests for description storage, draft injection, and confirm persistence |
| `tests/unit/test_configuration_agent.py` | Modify | Add tests for description injection in ConfigurationAgent prompt and ConsistencyCheckAgent JSON |

---

## Key design decisions

### Mocked tests only

No live tests added. All agents already have 3 live tests each. Description is an
optional field; LLM behavior with it is validated by the existing live tests running
the full flow.

### Follow existing patterns exactly

`_MockProvider` with `last_system`, `_json_response` / `_check_response` helpers,
`create_agent()` factory, `_make_data_lake()` temp dir. No new test infrastructure.

### Extend `_json_response` helper

Add optional `description: str | None = None` and `description_raw: str | None = None`
params so new tests can produce description-bearing responses without duplication.

### Extend `_MockProvider` with `last_user` in test_configuration_agent.py

ConsistencyCheckAgent puts `restaurant_description` in the JSON user message, not the
system prompt — `last_system` won't capture it. Extend the existing `_MockProvider`
with a `last_user: str = ""` field that records `messages[-1]["content"]` so the two
ConsistencyCheckAgent tests can assert on the user message content.

---

## Implementation steps

### `tests/unit/test_classification_agent.py`

#### Step 1 — Extend `_json_response` helper

Add `description` and `description_raw` optional params:

```python
def _json_response(
    reply: str = "Hola.",
    level: int | None = 2,
    description: str | None = None,
    description_raw: str | None = None,
) -> str:
    payload: dict[str, Any] = {"reply": reply}
    if level is not None:
        payload["standardization_level"] = level
    if description is not None:
        payload["description"] = description
    if description_raw is not None:
        payload["description_raw"] = description_raw
    return json.dumps(payload)
```

#### Step 2 — `TestClassificationAgent`: add 2 tests

**`test_run_stores_description_in_data_store`**
```python
def test_run_stores_description_in_data_store(self):
    response = _json_response(
        level=1,
        description="Taquería de barrio, servicio en mostrador",
        description_raw="tacos, mostrador",
    )
    agent, _ = self._make_agent(response=response)
    agent.run(input_data={"user_message": "Tacos, mostrador, colonia Roma."})
    self.assertEqual(
        agent.retrieve("restaurant_description"),
        "Taquería de barrio, servicio en mostrador",
    )
    self.assertEqual(agent.retrieve("restaurant_description_raw"), "tacos, mostrador")
```

**`test_description_injected_in_draft_after_capture`**
```python
def test_description_injected_in_draft_after_capture(self):
    response = _json_response(
        level=1,
        description="Taquería de barrio",
        description_raw="tacos, mostrador",
    )
    agent, provider = self._make_agent(response=response)
    agent.run(input_data={"user_message": "Primera vuelta."})
    agent.provider.response = _json_response(level=1)
    agent.run(input_data={"user_message": "Segunda vuelta."})
    self.assertIn("restaurant_description", provider.last_system)
```

#### Step 3 — `TestConfirmFn`: add 1 test

**`test_confirm_fn_persists_description`**
```python
def test_confirm_fn_persists_description(self):
    dl = _make_data_lake()
    confirm_fn = _make_confirm_fn(dl)
    session_id = "test_session_desc"
    draft = {
        "standardization_level": 1,
        "restaurant_description": "Taquería de barrio, servicio en mostrador",
        "restaurant_description_raw": "tacos, mostrador",
    }
    confirm_fn(draft, session_id)
    entity_id = abs(hash(session_id)) % (2**31 - 1)
    saved = dl.load_entity("classification", entity_id)
    self.assertEqual(saved["restaurant_description"], "Taquería de barrio, servicio en mostrador")
    self.assertEqual(saved["restaurant_description_raw"], "tacos, mostrador")
```

#### Step 4 — `TestClassificationStorage`: add 1 test

**`test_classification_save_load_round_trip_with_description`**
```python
def test_classification_save_load_round_trip_with_description(self):
    dl = _make_data_lake()
    data = {
        "standardization_level": 2,
        "restaurant_description": "Taquería de barrio",
        "restaurant_description_raw": "tacos y quesadillas",
    }
    dl.save_entity("classification", 1, data)
    loaded = dl.load_entity("classification", 1)
    self.assertEqual(loaded, data)
```

---

### `tests/unit/test_configuration_agent.py`

#### Step 5 — Extend `_MockProvider` with `last_user`

Add `last_user: str = ""` field and populate it from `messages[-1]["content"]`:

```python
class _MockProvider(LlmProvider):
    def __init__(self, response: str | None = None) -> None:
        super().__init__(model_name="mock")
        self.response = response or _config_response()
        self.last_system: str = ""
        self.last_user: str = ""

    def _do_generate(self, *, prompt, system, tools, structured_output,
                     messages, max_tokens, temperature) -> str:
        self.last_system = system or ""
        if messages:
            self.last_user = messages[-1].get("content", "")
        return self.response
```

#### Step 6 — `TestConfigurationAgent`: add 1 test

**`test_context_injects_restaurant_description`**
```python
def test_context_injects_restaurant_description(self):
    agent, provider = self._make_agent()
    agent.run(
        input_data={"user_message": "Hola"},
        context={
            "current_step": "categories",
            "restaurant_description": "Taquería de barrio, servicio en mostrador",
        },
    )
    self.assertIn("Taquería de barrio", provider.last_system)
```

#### Step 7 — `TestConsistencyCheckAgent`: add 2 tests

**`test_per_step_includes_restaurant_description`**
```python
def test_per_step_includes_restaurant_description(self):
    agent = self._make_agent(_check_response(looks_good=True))
    agent.run(input_data={
        "step": "categories",
        "entities": [{"name": "Comidas", "description": ""}],
        "restaurant_type": "Casual",
        "restaurant_description": "Taquería familiar",
    })
    user_json = json.loads(agent.provider.last_user)
    self.assertEqual(user_json.get("restaurant_description"), "Taquería familiar")
```

**`test_cross_entity_includes_restaurant_description`**
```python
def test_cross_entity_includes_restaurant_description(self):
    agent = self._make_agent(_check_response(looks_good=True))
    agent.run(input_data={
        "categories":             [{"name": "Comidas", "description": ""}],
        "families":               [{"name": "Lácteos", "description": ""}],
        "recipe_units":           [{"name": "gramo", "symbol": "g", "description": ""}],
        "inventory_units":        [{"name": "kg", "symbol": "kg", "is_standard": True, "description": ""}],
        "restaurant_type":        "Casual",
        "restaurant_description": "Taquería familiar",
    })
    user_json = json.loads(agent.provider.last_user)
    self.assertEqual(user_json.get("restaurant_description"), "Taquería familiar")
```

Note: these tests use `agent.provider.last_user` — requires the `_MockProvider` extension in Step 5.
The `_make_agent` helper in `TestConsistencyCheckAgent` returns a plain agent, not a tuple.
Access provider via `agent.provider`.

---

## Out of scope

- Changes to any production code
- New live tests
- Architecture doc updates
- CLAUDE.md / tasks.json status updates

---

## Risks and open questions

### `_MockProvider._do_generate` signature must match base class exactly

The `messages` parameter name and position must match `LlmProvider._do_generate` signature.
Verify against `core/ai/providers.py` before implementing Step 5.

---

## Deliverable checklist

### `tests/unit/test_classification_agent.py`
- [ ] `_json_response` helper extended to include optional `description` and `description_raw`
- [ ] `test_run_stores_description_in_data_store` — verifies both fields stored in `_data_store`
- [ ] `test_description_injected_in_draft_after_capture` — verifies draft injection on second turn
- [ ] `test_confirm_fn_persists_description` — verifies description saved to classification entity
- [ ] `test_classification_save_load_round_trip_with_description` — round-trip preserves description

### `tests/unit/test_configuration_agent.py`
- [ ] `_MockProvider` extended with `last_user` field
- [ ] `test_context_injects_restaurant_description` — description appears in ConfigurationAgent system prompt
- [ ] `test_per_step_includes_restaurant_description` — description in ConsistencyCheckAgent per-step JSON
- [ ] `test_cross_entity_includes_restaurant_description` — description in ConsistencyCheckAgent cross-entity JSON
