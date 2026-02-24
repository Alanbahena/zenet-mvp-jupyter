"""
LLM utility functions for parsing and validating structured outputs.

This module provides utilities for working with LLM responses, particularly
JSON-structured outputs that may be wrapped in markdown code fences.
"""

import json
from typing import Any

__all__ = ["parse_structured_output", "validate_structured_output"]


def parse_structured_output(raw: str) -> dict:
    """
    Parse JSON from LLM response, handling markdown code fences.

    Supports:
    - Clean JSON: {"name": "value"}
    - Fenced JSON: ```json\n{"name": "value"}\n```
    - Fenced without language: ```\n{"name": "value"}\n```

    Args:
        raw: Raw string response from LLM

    Returns:
        Parsed dictionary

    Raises:
        ValueError: If JSON is invalid or result is not a dict

    Examples:
        >>> parse_structured_output('{"name": "test"}')
        {'name': 'test'}

        >>> parse_structured_output('```json\\n{"name": "test"}\\n```')
        {'name': 'test'}
    """
    content = raw.strip()

    if not content:
        raise ValueError("Cannot parse empty string")

    # Handle markdown code fences (can appear anywhere in the response)
    fence_start = content.find("```")
    if fence_start != -1:
        # Find the first newline after opening fence
        first_newline = content.find("\n", fence_start)
        if first_newline == -1:
            raise ValueError("Invalid code fence format: no newline after opening fence")

        # Find closing fence
        closing_fence = content.find("```", first_newline)
        if closing_fence == -1:
            # No closing fence, try to parse rest of content after fence
            content = content[first_newline + 1:].strip()
        else:
            # Extract content between fences
            content = content[first_newline + 1:closing_fence].strip()

    # Parse JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        snippet = content[:100] + "..." if len(content) > 100 else content
        raise ValueError(f"Invalid JSON: {e.msg}. Input: {snippet}")

    # Validate it's a dict
    if not isinstance(data, dict):
        raise ValueError(f"Expected dict, got {type(data).__name__}")

    return data


def validate_structured_output(data: dict, required_keys: list[str]) -> bool:
    """
    Validate that all required keys are present in the data.

    Only checks top-level keys. Does not validate types or nested structures.

    Args:
        data: Parsed dictionary to validate
        required_keys: List of required top-level keys

    Returns:
        True if all keys present, False otherwise

    Examples:
        >>> validate_structured_output({"a": 1, "b": 2}, ["a", "b"])
        True

        >>> validate_structured_output({"a": 1}, ["a", "b"])
        False

        >>> validate_structured_output({"a": 1, "b": 2, "c": 3}, ["a"])
        True
    """
    return all(key in data for key in required_keys)
