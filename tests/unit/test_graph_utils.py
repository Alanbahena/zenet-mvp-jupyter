import unittest
from typing import TypedDict
from unittest.mock import MagicMock

from core.agents.graph_utils import make_agent_node, build_sequential_graph


class _TestState(TypedDict):
    session_id: str
    value: int


class TestMakeAgentNode(unittest.TestCase):

    def setUp(self):
        self.agent = MagicMock()

    def test_make_agent_node_calls_agent_run(self):
        self.agent.run.return_value = {"key": "val"}
        node = make_agent_node(self.agent, ["key"])
        node({"session_id": "s", "key": "input_val"})
        self.agent.run.assert_called_once()

    def test_make_agent_node_passes_correct_input_keys(self):
        self.agent.run.return_value = {}
        node = make_agent_node(self.agent, ["a", "b"])
        node({"session_id": "s", "a": 1, "b": 2, "c": 3})
        called_input = self.agent.run.call_args.kwargs["input_data"]
        self.assertEqual(set(called_input.keys()), {"a", "b", "session_id"})

    def test_make_agent_node_merges_result_into_state(self):
        self.agent.run.return_value = {"x": 1}
        node = make_agent_node(self.agent, [])
        result = node({"session_id": "s", "y": 2})
        self.assertIn("x", result)
        self.assertIn("y", result)

    def test_make_agent_node_missing_input_key_ignored(self):
        self.agent.run.return_value = {}
        node = make_agent_node(self.agent, ["missing"])
        node({"session_id": "s"})  # "missing" not in state — no error
        called_input = self.agent.run.call_args.kwargs["input_data"]
        self.assertEqual(set(called_input.keys()), {"session_id"})


class TestBuildSequentialGraph(unittest.TestCase):

    def test_build_sequential_graph_runs_end_to_end(self):
        node1 = lambda s: {**s, "value": s.get("value", 0) + 1}
        node2 = lambda s: {**s, "value": s.get("value", 0) + 10}
        graph = build_sequential_graph(
            nodes=[("n1", node1), ("n2", node2)],
            state_schema=_TestState,
        )
        result = graph.invoke({"session_id": "test", "value": 0})
        self.assertEqual(result["value"], 11)

    def test_build_sequential_graph_single_node(self):
        node = lambda s: {**s, "value": 42}
        graph = build_sequential_graph(
            nodes=[("only", node)],
            state_schema=_TestState,
        )
        result = graph.invoke({"session_id": "test", "value": 0})
        self.assertEqual(result["value"], 42)


if __name__ == "__main__":
    unittest.main()
