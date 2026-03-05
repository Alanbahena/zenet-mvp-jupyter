"""
LangGraph integration utilities for Zenet MVP 0.1.

Provides:
    BaseGraphState      -- base TypedDict all section graphs must extend
    make_agent_node()   -- wraps a BaseAgent as a LangGraph node function
    build_sequential_graph() -- builds and compiles a linear StateGraph
"""

from typing import TypedDict, Callable, Any
from langgraph.graph import StateGraph, END, START
from core.agents.base_agent import BaseAgent
from core.storage.persistence import DataLake


class BaseGraphState(TypedDict):
    session_id: str
    data_lake: DataLake


def make_agent_node(
    agent: BaseAgent,
    input_keys: list[str],
) -> Callable[[dict], dict]:
    """
    Wrap a BaseAgent as a LangGraph node function.

    The node reads input_keys from the graph state, calls agent.run(),
    and merges the result back into the state.

    Args:
        agent:      A BaseAgent instance.
        input_keys: Keys to extract from state and pass as input_data to agent.run().
                    session_id is always injected automatically from state.

    Returns:
        A node function: (state: dict) -> dict
    """
    def node(state: dict) -> dict:
        input_data = {k: state[k] for k in input_keys if k in state}
        input_data["session_id"] = state.get("session_id", "")
        result = agent.run(input_data=input_data)
        return {**state, **result}
    return node


def build_sequential_graph(
    nodes: list[tuple[str, Callable]],
    state_schema: type,
) -> Any:
    """
    Build and compile a simple linear LangGraph StateGraph.

    Args:
        nodes:        List of (node_name, node_fn) in execution order.
        state_schema: TypedDict class defining the graph state.

    Returns:
        Compiled LangGraph graph ready for .invoke().

    Raises:
        ValueError: If nodes is empty.
    """
    if not nodes:
        raise ValueError("nodes list must not be empty")
    graph = StateGraph(state_schema)
    for name, fn in nodes:
        graph.add_node(name, fn)
    graph.add_edge(START, nodes[0][0])
    for i in range(len(nodes) - 1):
        graph.add_edge(nodes[i][0], nodes[i + 1][0])
    graph.add_edge(nodes[-1][0], END)
    return graph.compile()
