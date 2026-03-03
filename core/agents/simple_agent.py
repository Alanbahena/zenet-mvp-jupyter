"""
RestaurantInfoAgent -- concrete minimal agent for framework validation.

Extracts restaurant name and type from a conversational message.
Models the core extraction pattern of the full Welcome Agent (Task 7).
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel

from core.agents.base_agent import BaseAgent


_SYSTEM_PROMPT = (
    "You are a restaurant data assistant. "
    "When the operator describes their restaurant, extract two pieces of information: "
    "the restaurant name (if mentioned) and the restaurant type "
    "(e.g. fast-casual, full-service, cafeteria, food truck)."
)


class _RestaurantInfoResponse(BaseModel):
    restaurant_name: str | None = None
    restaurant_type: str | None = None


class RestaurantInfoAgent(BaseAgent):
    """
    Minimal agent that extracts restaurant name and type from a conversation.

    Models the core interaction pattern of the full Welcome Agent (Task 7):
        - System prompt establishes role and extraction task
        - User provides information conversationally
        - Agent extracts structured data and stores it via self.store()

    This agent is for framework validation only. The full Welcome Agent (Task 7)
    extends this pattern with onboarding flow and notebook integration.

    Input:
        user_message: A message from the restaurant operator.

    Output:
        restaurant_name: Extracted name, or None if not mentioned.
        restaurant_type: Extracted type, or None if not mentioned.
        raw_response:    Full LLM response string before parsing.
    """

    INPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "user_message": "A message from the restaurant operator describing their restaurant.",
    }
    OUTPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "restaurant_name": "Extracted restaurant name, or None if not mentioned.",
        "restaurant_type": "Extracted restaurant type, or None if not mentioned.",
        "raw_response":    "Full LLM response string before parsing.",
    }
    RESPONSE_MODEL: ClassVar[type[BaseModel] | None] = _RestaurantInfoResponse

    def _generate_prompt(
        self,
        input_data: dict[str, Any],
        context: dict[str, Any],
    ) -> tuple[str, str]:
        return _SYSTEM_PROMPT, input_data["user_message"]

    def _process_response(self, response: str) -> dict[str, Any]:
        data = self._parse_response(response)
        self.store("restaurant_name", data.get("restaurant_name"))
        self.store("restaurant_type", data.get("restaurant_type"))
        return {
            "restaurant_name": data.get("restaurant_name"),
            "restaurant_type": data.get("restaurant_type"),
            "raw_response": response,
        }
