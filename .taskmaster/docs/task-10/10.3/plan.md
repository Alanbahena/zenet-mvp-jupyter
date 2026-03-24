# Subtask 10.3 — CANCELLED

## Status: Cancelled

**Reason:** After reviewing the actual codebase, no existing Gradio section (bienvenida,
clasificación, configuración) uses LangGraph. All sections call agents directly from the
Gradio handler. Introducing LangGraph here for a single-agent conversational section would
add indirection without benefit — one agent means no orchestration value, and the
"conditional branching" (file vs conversation) is a simple `if/else` in the handler.

**Original goal (for reference):** Add `build_conditional_graph()` to `graph_utils.py`
and define `AlignmentGraphState` so the Gradio section could wire a file-path vs
conversation-path branching graph.

**LangGraph use cases for future reference:**
- Multi-agent fan-out (e.g. parallel UnitResolver + PriceEstimator + NutritionAgent)
- Retry loops with a quality-gate agent (e.g. AlignmentAgent → ConsistencyCheckAgent → loop back)
- Full onboarding pipeline (all sections in sequence, no UI, API-only)

## Deferred to subtask 10.4

File parsing libraries were listed as a prerequisite in the parent plan but are not yet
installed. Add at the start of 10.4 before any implementation:

```bash
uv add pypdf openpyxl pillow
```

- `pypdf` — PDF text extraction
- `openpyxl` — Excel files (.xlsx)
- `pillow` — image files (photos of handwritten recipes)

**Builds on:** 10.2 delivered `AlignmentAgent` — the callable node for the graph.
**Required by:** 10.4 — imports `AlignmentGraphState`, `build_conditional_graph`,
and `make_agent_node` to build and invoke the running graph.

---

## Dependencies

- Subtask 10.1 done: `BaseGraphState` in `graph_utils.py` (`session_id`, `data_lake`)
- Subtask 10.2 done: `AlignmentAgent` in `core/agents/alignment_agent.py`
- `langgraph` installed (already confirmed in environment)
- `StateGraph`, `END`, `START` already imported in `graph_utils.py`

---

## Key design decisions

| Decision | Rationale |
|----------|-----------|
| `AlignmentGraphState` lives in `graph_utils.py` | Consistent with `BaseGraphState` placement; all graph state types co-located |
| `build_conditional_graph` added to `graph_utils.py` | Generic helper mirrors `build_sequential_graph`; keeps graph utilities co-located |
| `build_sequential_graph` left strictly unchanged | Backwards-compatible — bienvenida, clasificación, configuración callers must not break |
| Terminal edges (`→ END`) are caller's responsibility | Keeps the helper generic; 10.4 adds terminal edges when building the actual graph |
| Condition function returns a string key | Matches LangGraph `add_conditional_edges(source, path_fn, path_map)` API — `path_fn` returns a string that indexes into `path_map` |

---

## Files to modify / create

| File | Action | Summary |
|------|--------|---------|
| `core/agents/graph_utils.py` | Modify | Add `AlignmentGraphState` TypedDict + `build_conditional_graph()` |

---

## Implementation steps

### Step 1 — Add `AlignmentGraphState` to `graph_utils.py`

Place immediately after `BaseGraphState` (line 19):

```python
class AlignmentGraphState(BaseGraphState):
    """Graph state for the Alineamiento section.

    Extends BaseGraphState with recipe-capture fields that accumulate across nodes.
    recipe_draft and inventory_proposals are updated in-place by AlignmentAgent.
    """
    recipe_source: str           # "file_content" | "conversation"
    recipe_count: int | None     # operator-stated recipe count; None if skipped
    current_page_index: int      # 0-based index into multi-recipe file or session
    recipe_draft: dict           # accumulated draft from AlignmentAgent._process_response()
    inventory_proposals: list    # proposal list from AlignmentAgent._process_response()
    user_message: str            # current operator turn message
```

Constraints:
- Must extend `BaseGraphState` (not `TypedDict` directly) so `session_id` and `data_lake` are inherited
- `recipe_count: int | None` — `None` means operator skipped count; displayed as `"?"` in UI progress indicator
- `recipe_draft` and `inventory_proposals` default to empty `{}` / `[]` at graph init; 10.4 is responsible for initialization

### Step 2 — Add `build_conditional_graph()` to `graph_utils.py`

Place after `build_sequential_graph`. No changes to `build_sequential_graph`.

```python
def build_conditional_graph(
    nodes: list[tuple[str, Callable]],
    conditional_edges: list[tuple[str, Callable, dict[str, str]]],
    state_schema: type,
) -> Any:
    """
    Build and compile a LangGraph StateGraph with conditional branching.

    Args:
        nodes:             List of (node_name, node_fn) — all nodes in the graph.
        conditional_edges: List of (source_node, condition_fn, route_map).
                           condition_fn(state) -> str; route_map maps that string to
                           a target node name or END.
        state_schema:      TypedDict class defining the graph state.

    Returns:
        Compiled LangGraph graph ready for .invoke().

    Raises:
        ValueError: If nodes is empty or conditional_edges is empty.

    Note:
        Terminal edges (→ END) are NOT added automatically. The caller must include
        END as a value in the route_map of the final conditional edge, or add linear
        edges after calling this function on the compiled graph (not supported by
        LangGraph). Design topology so all paths reach END via the route_map.
    """
    if not nodes:
        raise ValueError("nodes list must not be empty")
    if not conditional_edges:
        raise ValueError("conditional_edges list must not be empty")
    graph = StateGraph(state_schema)
    for name, fn in nodes:
        graph.add_node(name, fn)
    graph.add_edge(START, nodes[0][0])
    for source_node, condition_fn, route_map in conditional_edges:
        graph.add_conditional_edges(source_node, condition_fn, route_map)
    return graph.compile()
```

### Step 3 — Verify graph topology expressible via the API

The alignment graph topology from the parent plan:

```
START
  └── initial_questions_node
          ├── "file_content"   → file_extraction_node  → END
          └── "conversation"   → conversational_node   → END
```

This maps to a single conditional edge call:

```python
build_conditional_graph(
    nodes=[
        ("initial_questions_node", initial_questions_fn),
        ("file_extraction_node", file_extraction_fn),
        ("conversational_node", conversational_fn),
    ],
    conditional_edges=[
        (
            "initial_questions_node",
            lambda state: state["recipe_source"],
            {
                "file_content": "file_extraction_node",
                "conversation": "conversational_node",
            },
        )
    ],
    state_schema=AlignmentGraphState,
)
```

`file_extraction_node` and `conversational_node` implicitly reach `END` because
LangGraph treats nodes with no outgoing edges as terminal. 10.4 will define the
actual node functions and call `build_conditional_graph`.

**Note:** The parent plan also shows a `review_node` downstream of `conversational_node`.
If added, 10.4 wires it as a linear edge after the branch. `build_conditional_graph`
does not need to change — 10.4 can add `graph.add_edge("conversational_node", "review_node")`
before compiling, OR the helper can be extended then. Defer to 10.4.

---

## Out of scope

- Actual node functions (`initial_questions_node`, `file_extraction_node`, `conversational_node`, `review_node`) — 10.4
- File parsing (PDF, Excel, image) — 10.4
- `AlignmentAgent` modifications — 10.2 is complete
- Exports (`__init__.py`) — 10.5
- Tests — 10.5 (see risks below)
- Any existing graphs (bienvenida, clasificación, configuración) — must not change

---

## Risks and open questions

### [OPEN] — No mocked tests for `build_conditional_graph` in the 10.5 test table
**Source:** Breakdown validation of subtask 10.3
**Problem:** The parent plan's test table (test_alignment_agent.py, 21 tests) has no
test for `build_conditional_graph` or `AlignmentGraphState`. Both are pure offline logic.
**Impact:** Routing bug (wrong branch taken) would only surface at Gradio integration time.
**Suggested action:** Add at 10.5 — recommend at minimum:
- `test_build_conditional_graph_routes_file_content` — verifies branch to `file_extraction_node`
- `test_build_conditional_graph_routes_conversation` — verifies branch to `conversational_node`
- `test_alignment_graph_state_inherits_base_keys` — `session_id` and `data_lake` present

### [OPEN] — `review_node` placement deferred to 10.4
**Source:** Parent plan graph topology (step 10)
**Problem:** Parent plan shows `review_node` downstream of `conversational_node`, but its
node function is defined in 10.4. `build_conditional_graph` as designed can't add a linear
edge after the branch — 10.4 must handle this.
**Impact:** If 10.4 needs a different helper signature (e.g. `linear_edges` param), 10.3
must be revisited.
**Suggested action:** At 10.4 planning time, decide: inline `graph.add_edge(...)` after
`build_conditional_graph`, or extend the helper.

---

## Deliverable checklist

### `core/agents/graph_utils.py`
- [ ] `AlignmentGraphState(BaseGraphState)` TypedDict added with 6 fields: `recipe_source`, `recipe_count`, `current_page_index`, `recipe_draft`, `inventory_proposals`, `user_message`
- [ ] `build_conditional_graph(nodes, conditional_edges, state_schema)` added
- [ ] `build_conditional_graph` raises `ValueError` if `nodes` or `conditional_edges` is empty
- [ ] `build_sequential_graph` unchanged (no edits)
- [ ] No new imports required (all dependencies already imported in `graph_utils.py`)
