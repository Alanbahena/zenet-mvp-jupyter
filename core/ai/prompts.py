"""
Prompt templating utilities for LLM interactions.

Provides PromptTemplate dataclass and helper functions for building
consistent prompts across agents. Includes pre-built templates for
common restaurant operations.
"""

from dataclasses import dataclass
from typing import Any

__all__ = [
    "PromptTemplate",
    "format_system_prompt",
    "format_user_prompt",
    "INGREDIENT_EXTRACTION_PROMPT",
    "RECIPE_CLASSIFICATION_PROMPT",
    "INVENTORY_ITEM_SUGGESTION_PROMPT",
]


@dataclass
class PromptTemplate:
    """
    Template for LLM prompts with variable substitution.

    Attributes:
        name: Identifier for this template (e.g., "ingredient_extraction")
        system: System prompt (role, context, instructions)
        user_template: User prompt template with {variable} placeholders

    Example:
        >>> template = PromptTemplate(
        ...     name="recipe_analysis",
        ...     system="You are a recipe analyst.",
        ...     user_template="Analyze this recipe: {recipe_text}"
        ... )
        >>> system, user = template.render(recipe_text="Pasta carbonara...")
        >>> print(system)
        You are a recipe analyst.
        >>> print(user)
        Analyze this recipe: Pasta carbonara...
    """

    name: str
    system: str
    user_template: str

    def render(self, **kwargs: Any) -> tuple[str, str]:
        """
        Render the template with provided variables.

        Args:
            **kwargs: Variables to substitute in user_template

        Returns:
            Tuple of (system_prompt, user_prompt)

        Raises:
            KeyError: If a required variable is not provided

        Example:
            >>> template = PromptTemplate(
            ...     name="test",
            ...     system="You are helpful.",
            ...     user_template="Process {item}"
            ... )
            >>> system, user = template.render(item="data")
            >>> user
            'Process data'
        """
        user_prompt = self.user_template.format_map(kwargs)
        return (self.system, user_prompt)


def format_system_prompt(role: str, context: str | None = None) -> str:
    """
    Build a system prompt from role and optional context.

    Args:
        role: The role description (e.g., "recipe analyst", "inventory manager")
        context: Optional additional context (e.g., "for an Italian restaurant")

    Returns:
        Formatted system prompt string

    Example:
        >>> format_system_prompt("recipe analyst")
        'You are a recipe analyst.'

        >>> format_system_prompt("recipe analyst", "for an Italian restaurant")
        'You are a recipe analyst for an Italian restaurant.'
    """
    if context:
        return f"You are a {role} {context}."
    return f"You are a {role}."


def format_user_prompt(template: str, **kwargs: Any) -> str:
    """
    Format a user prompt template with variables.

    Simple wrapper around str.format_map() for consistency.

    Args:
        template: Template string with {variable} placeholders
        **kwargs: Variables to substitute

    Returns:
        Formatted prompt string

    Raises:
        KeyError: If a required variable is not provided

    Example:
        >>> format_user_prompt("Extract ingredients from: {text}", text="Pasta recipe...")
        'Extract ingredients from: Pasta recipe...'
    """
    return template.format_map(kwargs)


# Pre-built template 1: Ingredient extraction
INGREDIENT_EXTRACTION_PROMPT = PromptTemplate(
    name="ingredient_extraction",
    system=format_system_prompt(
        "ingredient extraction specialist",
        "helping restaurant operators structure their recipe data",
    ),
    user_template="""Extract all ingredients from the following recipe text and return them as a JSON array.

Each ingredient should have:
- name (string): ingredient name
- quantity (number or null if not specified)
- unit (string or null if not specified)

Recipe text:
{recipe_text}

Return only valid JSON, no additional text.""",
)


# Pre-built template 2: Recipe classification
RECIPE_CLASSIFICATION_PROMPT = PromptTemplate(
    name="recipe_classification",
    system=format_system_prompt("recipe classification specialist", "for restaurant operations"),
    user_template="""Classify this recipe into the appropriate category.

Available categories: {categories}

Recipe:
Name: {recipe_name}
Description: {recipe_description}

Return JSON with the structure:
{{"category": "category_name", "confidence": 0.0-1.0}}""",
)


# Pre-built template 3: Inventory item suggestion
INVENTORY_ITEM_SUGGESTION_PROMPT = PromptTemplate(
    name="inventory_item_suggestion",
    system=format_system_prompt(
        "inventory management assistant",
        "helping organize restaurant inventory",
    ),
    user_template="""Given this ingredient from a recipe, suggest the corresponding inventory item.

Ingredient: {ingredient_name}
Recipe context: {recipe_name}

Available inventory families: {families}

Return JSON:
{{"inventory_item_name": "suggested name", "family": "family_name", "reasoning": "brief explanation"}}""",
)
