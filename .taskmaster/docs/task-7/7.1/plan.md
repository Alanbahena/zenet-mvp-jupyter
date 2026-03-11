# Subtask 7.1 — WelcomeAgent (`core/agents/welcome_agent.py`)

## Context

**Parent task:** Task 7 — Bienvenida Section: Welcome Agent + Onboarding Form
**Source of truth:** `.taskmaster/docs/task-7/plan.md`

This subtask creates `WelcomeAgent`, the Spanish-language companion agent for the
Bienvenida chat panel. It is the first concrete output of Task 7 and the dependency
that subtasks 7.3 (bienvenida UI) and 7.6 (tests) are blocked on.

**Prior (Tasks 5–6):** Delivered `BaseAgent`, `create_agent()`, `ConversationMemory`,
`DataLake`, and the Gradio shell. Everything `WelcomeAgent` extends is already in place.

**Next (7.2):** Modifies `components.py` — no direct dependency on `WelcomeAgent`.
**Next (7.3):** Imports `WelcomeAgent` into `bienvenida.py` — cannot be written until
this file exists.

---

## Scope

| In scope | Out of scope |
|----------|-------------|
| `core/agents/welcome_agent.py` | `core/__init__.py` re-export (subtask 7.5) |
| `WelcomeAgent(BaseAgent)` class | `bienvenida.py` wiring (subtask 7.3) |
| `_SYSTEM_PROMPT` in Spanish | `tests/unit/test_welcome_agent.py` (subtask 7.6) |
| Context-aware personalization | LangGraph graph (excluded from entire Task 7) |
| Module docstring and class docstring | Tool calling |

---

## Architectural Decisions

### Decision 1: `RESPONSE_MODEL = None` — plain prose, not JSON

**Choice:** `RESPONSE_MODEL: ClassVar[type[BaseModel] | None] = None`

**Rationale:** The agent is a companion, not a data extractor. `RESPONSE_MODEL = None`
causes `BaseAgent._generate_response()` to pass `structured_output=False` to the
provider (line 313 of `base_agent.py`), so no JSON-forcing instruction is added.

---

### Decision 2: No `self.store()` — agent does not write to data store

**Choice:** `_process_response` returns `{"reply": response, "raw_response": response}` with no `self.store()` call.

**Rationale:** WelcomeAgent is a companion only. The form (`bienvenida.py`) handles
all data capture. Mixing data extraction into the chat agent would complicate
validation and error recovery.

---

### Decision 3: No `self._parse_response()` — response is plain text

**Choice:** Return `response` directly without passing through `_parse_response()`.

**Rationale:** `_parse_response()` attempts JSON parsing and Pydantic validation.
When `RESPONSE_MODEL = None` and the LLM returns natural language, calling
`_parse_response()` would return `{}`. Return the raw string directly.

---

### Decision 4: Context-aware system prompt personalization

**Choice:** `_generate_prompt` checks `context.get("operator_name")` and, if truthy,
appends a personalization line to the system prompt before returning it.

**Rationale:** When the operator has already filled in the form, `_load_form_context`
(in `bienvenida.py`) injects their name into context. The agent can then address
them by name, making the interaction warmer without changing the base prompt.

---

## File to Create

| File | Action | Summary |
|------|--------|---------|
| `core/agents/welcome_agent.py` | Create | `WelcomeAgent(BaseAgent)` — companion agent, plain-text Spanish |

---

## Reference Pattern

Follow `core/agents/simple_agent.py` (`RestaurantInfoAgent`) exactly for:
- Module structure (docstring → imports → `_SYSTEM_PROMPT` → class)
- `ClassVar` attribute ordering (`INPUT_SCHEMA`, `OUTPUT_SCHEMA`, `RESPONSE_MODEL`)
- Method signatures for `_generate_prompt` and `_process_response`

Key differences from `RestaurantInfoAgent`:
- No Pydantic response model class
- `RESPONSE_MODEL = None` (not a Pydantic class)
- `_process_response` returns raw text directly (no `_parse_response()`)
- `_generate_prompt` reads from `context` for personalization
- No `self.store()` calls

---

## Implementation Steps

### Step 1 — File header and imports

```python
"""
WelcomeAgent -- companion agent for the Bienvenida onboarding section.

Provides warm, supportive conversation in Spanish to help restaurant operators
understand Zenet and reduce onboarding anxiety. Does NOT extract or store data --
the onboarding form handles data capture.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel

from core.agents.base_agent import BaseAgent
```

Import `BaseModel` from pydantic even though no model is defined here — needed for
the `ClassVar[type[BaseModel] | None]` annotation. Matches `simple_agent.py` style.

---

### Step 2 — Module-level `_SYSTEM_PROMPT`

Write a Spanish string that:
- Introduces the agent as "Zeni", the Zenet assistant
- Explains Zenet's 6-section pipeline when asked: Bienvenida → Clasificación →
  Configuración inicial → Alineamiento → Estructura → Manual operativo
- Validates operator anxiety (empathetic tone — many operators are first-time software users)
- Does NOT ask to extract or store information
- Keeps responses to 2–4 sentences

Example structure (implementer writes the actual text):
```python
_SYSTEM_PROMPT = (
    "Eres Zeni, la asistente de bienvenida de Zenet. ..."
    "Tu función es acompañar al operador durante el proceso de registro, ..."
    "NO recopiles datos — el formulario se encarga de eso. ..."
)
```

---

### Step 3 — `WelcomeAgent` class

```python
class WelcomeAgent(BaseAgent):
    """
    Companion agent for the Bienvenida section.

    Provides warm conversational support in Spanish. Does not extract data.

    Input:
        user_message: A message from the restaurant operator.

    Output:
        reply:        The agent's conversational response (plain text).
        raw_response: Same as reply (no parsing applied).
    """

    INPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "user_message": "A message from the restaurant operator.",
    }
    OUTPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "reply":        "The agent's conversational response in Spanish.",
        "raw_response": "Full LLM response string (same as reply).",
    }
    RESPONSE_MODEL: ClassVar[type[BaseModel] | None] = None
```

Constraint: no `@dataclass` decorator on the class — matches `RestaurantInfoAgent`.
`WelcomeAgent` inherits dataclass behaviour from `BaseAgent`.

---

### Step 4 — `_generate_prompt`

```python
def _generate_prompt(
    self,
    input_data: dict[str, Any],
    context: dict[str, Any],
) -> tuple[str, str]:
    system = _SYSTEM_PROMPT
    if context.get("operator_name"):
        system = f"{system}\n\nEl operador se llama {context['operator_name']}."
    return system, input_data["user_message"]
```

Constraint: personalization is appended as a new paragraph, not merged into the
base prompt string. The base `_SYSTEM_PROMPT` constant must remain unmodified.

---

### Step 5 — `_process_response`

```python
def _process_response(self, response: str) -> dict[str, Any]:
    return {"reply": response, "raw_response": response}
```

Constraint: no `self._parse_response()`, no `self.store()`. Both `reply` and
`raw_response` are the same string — kept distinct in the schema for consistency
with other agents and forward compatibility.

---

## How Memory Works

`WelcomeAgent` does not override any memory logic — it inherits everything from
`BaseAgent`:

- `memory: ConversationMemory` is a dataclass field (default fresh instance)
- `run()` calls `self.memory.add_user(user_prompt)` → LLM → `self.memory.add_assistant(response)`
- `self.memory.get_messages()` passes full history to the LLM on every turn

Cross-turn persistence is handled in `bienvenida.py` (subtask 7.3):
```
create_agent(WelcomeAgent, ...)       # fresh agent, empty memory
agent.load_state(data_lake, session_id=f"welcome_agent_{session_id}")
agent.run(...)                        # appends 2 messages to memory
agent.save_state(data_lake, session_id=f"welcome_agent_{session_id}")
```

State is stored as `{"agent_name": ..., "memory": {...}, "data_store": {}}` under
entity type `"agent_state"` in `DataLake`.

---

## Dependencies

- `core/agents/base_agent.py` — `BaseAgent` (confirmed present ✓)
- `core/agents/utils.py` — `create_agent()` (confirmed present ✓)
- `pydantic` — `BaseModel` for type annotation (installed via `uv sync` ✓)
- No `ANTHROPIC_API_KEY` needed for this subtask (no LLM call here)
- Tasks 5 & 6 marked `done` in `tasks.json` (confirmed ✓)

---

## Risks and Open Questions

1. **`_SYSTEM_PROMPT` content is left to the implementer.** The plan specifies tone
   and structure but not literal text. The prompt should be tested with a live API
   call (subtask 7.6 live tests) to verify tone, language, and pipeline description
   accuracy.

2. **Personalization phrasing.** `"El operador se llama {name}."` is a suggested
   format. A warmer alternative: `"Puedes llamar al operador por su nombre: {name}."`.
   Either is acceptable — choose one and keep it consistent with test assertions in 7.6.

3. **`pydantic.BaseModel` import with no model defined.** Importing `BaseModel` only
   for the type annotation is slightly unusual. Alternative: use `type[Any] | None`
   or a string annotation. The recommended approach is to import `BaseModel` to match
   `simple_agent.py` exactly, even if no model class is defined.

---

## Deliverable Checklist

- [ ] `WelcomeAgent` dataclass extending `BaseAgent`
- [ ] `INPUT_SCHEMA` with `user_message` key
- [ ] `OUTPUT_SCHEMA` with `reply` and `raw_response` keys
- [ ] `RESPONSE_MODEL = None`
- [ ] `_SYSTEM_PROMPT` in Spanish (warm, companion tone, 6-section pipeline reference)
- [ ] `_generate_prompt()` with optional `operator_name` personalization from context
- [ ] `_process_response()` returning plain text as `reply` and `raw_response`

## Verification

```bash
# Smoke test (no API key needed)
uv run python -c "
from core.agents.utils import create_agent
from core.agents.welcome_agent import WelcomeAgent
from core.ai.providers import ClaudeProvider

class _FakeProvider:
    model_name = 'mock'
    def generate(self, **kw): return 'Hola, soy Zeni.'
    def generate_raw(self, **kw): pass

agent = create_agent(WelcomeAgent, provider=_FakeProvider(), name='zeni')
result = agent.run(input_data={'user_message': 'Hola'})
assert 'reply' in result and 'raw_response' in result
print('OK:', result)
"

# Full mocked test suite (after 7.6 is written)
uv run python -m pytest tests/unit/test_welcome_agent.py -v
```
