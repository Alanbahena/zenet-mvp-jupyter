"""
Manual wiring validation for LangGraph integration pattern.

Demonstrates the full pipeline:
    create_agent() -> make_agent_node() -> build_sequential_graph() -> graph.invoke()

Requires ANTHROPIC_API_KEY in .env. Not run in the unit test suite.
Run manually:
    uv run python examples/graph_example.py
"""

import sys
from pathlib import Path

# Ensure project root is on path so gradio_app and core are importable
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from typing import Optional

from gradio_app.session import get_data_lake, create_session
from core.agents import create_agent, RestaurantInfoAgent
from core.agents.graph_utils import BaseGraphState, make_agent_node, build_sequential_graph
from core.ai.providers import ClaudeProvider


class ExampleState(BaseGraphState):
    user_message: str
    restaurant_name: Optional[str]
    restaurant_type: Optional[str]


provider = ClaudeProvider()  # defaults to claude-sonnet-4-6; reads ANTHROPIC_API_KEY from .env

agent_a = create_agent(RestaurantInfoAgent, provider=provider, name="extractor")
agent_b = create_agent(RestaurantInfoAgent, provider=provider, name="confirmer")

graph = build_sequential_graph(
    nodes=[
        ("extract", make_agent_node(agent_a, input_keys=["user_message"])),
        ("confirm", make_agent_node(agent_b, input_keys=["restaurant_name", "user_message"])),
    ],
    state_schema=ExampleState,
)

data_lake = get_data_lake()
session_id = create_session(data_lake)

result = graph.invoke({
    "session_id": session_id,
    "data_lake": data_lake,
    "user_message": "Mi restaurante se llama El Rincón y es de tipo fast-casual.",
    "restaurant_name": None,
    "restaurant_type": None,
})
print(result)
