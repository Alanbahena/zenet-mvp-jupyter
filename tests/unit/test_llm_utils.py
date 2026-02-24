"""
Unit tests for LLM utility functions.

Tests parse_structured_output and validate_structured_output with various
input formats, edge cases, and error conditions.
"""

import unittest

from core.ai.utils import parse_structured_output, validate_structured_output


class TestParseStructuredOutput(unittest.TestCase):
    """Tests for parse_structured_output function."""

    def test_clean_json_dict(self):
        """Test parsing clean JSON dictionary."""
        raw = '{"name": "test", "value": 123}'
        result = parse_structured_output(raw)
        self.assertEqual(result, {"name": "test", "value": 123})

    def test_fenced_json_with_language(self):
        """Test parsing JSON wrapped in ```json fences."""
        raw = '```json\n{"name": "test"}\n```'
        result = parse_structured_output(raw)
        self.assertEqual(result, {"name": "test"})

    def test_fenced_json_without_language(self):
        """Test parsing JSON wrapped in ``` fences without language."""
        raw = '```\n{"name": "test"}\n```'
        result = parse_structured_output(raw)
        self.assertEqual(result, {"name": "test"})

    def test_fenced_json_with_extra_whitespace(self):
        """Test parsing fenced JSON with extra whitespace."""
        raw = '  \n```json\n  {"name": "test"}  \n```\n  '
        result = parse_structured_output(raw)
        self.assertEqual(result, {"name": "test"})

    def test_clean_json_with_whitespace(self):
        """Test parsing clean JSON with leading/trailing whitespace."""
        raw = '  \n{"name": "test"}\n  '
        result = parse_structured_output(raw)
        self.assertEqual(result, {"name": "test"})

    def test_complex_nested_dict(self):
        """Test parsing complex nested dictionary."""
        raw = '{"recipe": {"name": "pasta", "ingredients": [{"name": "egg", "qty": 2}]}}'
        result = parse_structured_output(raw)
        self.assertEqual(result, {
            "recipe": {
                "name": "pasta",
                "ingredients": [{"name": "egg", "qty": 2}]
            }
        })

    def test_fenced_json_incomplete_closing_fence(self):
        """Test parsing fenced JSON without closing fence."""
        raw = '```json\n{"name": "test"}'
        result = parse_structured_output(raw)
        self.assertEqual(result, {"name": "test"})

    def test_multiple_code_fences_takes_first(self):
        """Test that multiple code blocks returns first block."""
        raw = '```json\n{"first": 1}\n```\n```json\n{"second": 2}\n```'
        result = parse_structured_output(raw)
        self.assertEqual(result, {"first": 1})

    def test_fence_with_extra_text_after(self):
        """Test fenced JSON with extra text after closing fence."""
        raw = '```json\n{"name": "test"}\n```\nExtra text here'
        result = parse_structured_output(raw)
        self.assertEqual(result, {"name": "test"})

    def test_empty_string_raises_error(self):
        """Test that empty string raises ValueError."""
        with self.assertRaises(ValueError) as context:
            parse_structured_output('')
        self.assertIn("empty string", str(context.exception).lower())

    def test_whitespace_only_raises_error(self):
        """Test that whitespace-only string raises ValueError."""
        with self.assertRaises(ValueError) as context:
            parse_structured_output('   \n  \t  ')
        self.assertIn("empty string", str(context.exception).lower())

    def test_invalid_json_raises_error(self):
        """Test that invalid JSON raises ValueError."""
        with self.assertRaises(ValueError) as context:
            parse_structured_output('{"name": invalid}')
        self.assertIn("Invalid JSON", str(context.exception))

    def test_json_list_raises_error(self):
        """Test that JSON list raises ValueError."""
        with self.assertRaises(ValueError) as context:
            parse_structured_output('[1, 2, 3]')
        self.assertIn("Expected dict, got list", str(context.exception))

    def test_json_string_raises_error(self):
        """Test that JSON string raises ValueError."""
        with self.assertRaises(ValueError) as context:
            parse_structured_output('"just a string"')
        self.assertIn("Expected dict, got str", str(context.exception))

    def test_json_number_raises_error(self):
        """Test that JSON number raises ValueError."""
        with self.assertRaises(ValueError) as context:
            parse_structured_output('42')
        self.assertIn("Expected dict, got int", str(context.exception))

    def test_json_boolean_raises_error(self):
        """Test that JSON boolean raises ValueError."""
        with self.assertRaises(ValueError) as context:
            parse_structured_output('true')
        self.assertIn("Expected dict, got bool", str(context.exception))

    def test_unclosed_brace_raises_error(self):
        """Test that unclosed JSON raises ValueError."""
        with self.assertRaises(ValueError) as context:
            parse_structured_output('{"name": "test"')
        self.assertIn("Invalid JSON", str(context.exception))

    def test_error_message_includes_snippet(self):
        """Test that error message includes input snippet."""
        long_input = '{"invalid": ' + 'x' * 200 + '}'
        with self.assertRaises(ValueError) as context:
            parse_structured_output(long_input)
        error_msg = str(context.exception)
        self.assertIn("Invalid JSON", error_msg)
        # Should include snippet, not full input
        self.assertTrue(len(error_msg) < len(long_input))

    def test_fence_without_newline_raises_error(self):
        """Test that fence without newline raises ValueError."""
        with self.assertRaises(ValueError) as context:
            parse_structured_output('```{"name": "test"}```')
        self.assertIn("Invalid code fence format", str(context.exception))


class TestValidateStructuredOutput(unittest.TestCase):
    """Tests for validate_structured_output function."""

    def test_all_keys_present(self):
        """Test validation with all required keys present."""
        data = {"a": 1, "b": 2, "c": 3}
        result = validate_structured_output(data, ["a", "b"])
        self.assertTrue(result)

    def test_exact_keys_match(self):
        """Test validation with exact key match."""
        data = {"name": "test", "value": 123}
        result = validate_structured_output(data, ["name", "value"])
        self.assertTrue(result)

    def test_extra_keys_allowed(self):
        """Test that extra keys are allowed."""
        data = {"a": 1, "b": 2, "c": 3}
        result = validate_structured_output(data, ["a"])
        self.assertTrue(result)

    def test_empty_required_keys(self):
        """Test validation with empty required keys list."""
        data = {"anything": "here"}
        result = validate_structured_output(data, [])
        self.assertTrue(result)

    def test_single_key_present(self):
        """Test validation with single required key present."""
        data = {"name": "test"}
        result = validate_structured_output(data, ["name"])
        self.assertTrue(result)

    def test_none_value_counts_as_present(self):
        """Test that key with None value counts as present."""
        data = {"a": None, "b": 2}
        result = validate_structured_output(data, ["a", "b"])
        self.assertTrue(result)

    def test_missing_key_returns_false(self):
        """Test validation with missing required key."""
        data = {"a": 1}
        result = validate_structured_output(data, ["a", "b"])
        self.assertFalse(result)

    def test_empty_data_returns_false(self):
        """Test validation with empty data dict."""
        data = {}
        result = validate_structured_output(data, ["a"])
        self.assertFalse(result)

    def test_multiple_missing_keys_returns_false(self):
        """Test validation with multiple missing keys."""
        data = {"a": 1}
        result = validate_structured_output(data, ["b", "c", "d"])
        self.assertFalse(result)

    def test_empty_data_empty_keys_returns_true(self):
        """Test validation with empty data and empty required keys."""
        data = {}
        result = validate_structured_output(data, [])
        self.assertTrue(result)

    def test_case_sensitive_keys(self):
        """Test that key validation is case-sensitive."""
        data = {"Name": "test"}
        result = validate_structured_output(data, ["name"])
        self.assertFalse(result)

    def test_single_missing_key_returns_false(self):
        """Test validation with one missing key out of many."""
        data = {"a": 1, "b": 2, "c": 3}
        result = validate_structured_output(data, ["a", "b", "c", "d"])
        self.assertFalse(result)


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests combining parse and validate."""

    def test_parse_then_validate_success(self):
        """Test typical workflow: parse then validate successfully."""
        raw = '```json\n{"name": "Pasta", "servings": 4, "time": 30}\n```'
        data = parse_structured_output(raw)
        is_valid = validate_structured_output(data, ["name", "servings"])
        self.assertTrue(is_valid)
        self.assertEqual(data["name"], "Pasta")

    def test_parse_then_validate_missing_key(self):
        """Test workflow where validation fails due to missing key."""
        raw = '{"name": "Pasta", "time": 30}'
        data = parse_structured_output(raw)
        is_valid = validate_structured_output(data, ["name", "servings"])
        self.assertFalse(is_valid)

    def test_parse_error_prevents_validation(self):
        """Test that parse error prevents reaching validation."""
        raw = '{"invalid": json}'
        with self.assertRaises(ValueError):
            data = parse_structured_output(raw)
            # Should not reach here
            validate_structured_output(data, ["name"])

    def test_real_world_llm_response(self):
        """Test with realistic LLM response format."""
        raw = '''Here's the recipe data you requested:

```json
{
  "restaurant_type": "pizzeria",
  "cuisine": "italian",
  "categories": ["appetizers", "mains", "desserts"]
}
```

Let me know if you need anything else!'''

        data = parse_structured_output(raw)
        self.assertEqual(data["restaurant_type"], "pizzeria")
        self.assertTrue(validate_structured_output(data, ["restaurant_type", "cuisine"]))

    def test_minimal_response(self):
        """Test with minimal valid response."""
        raw = '{}'
        data = parse_structured_output(raw)
        # Empty dict with no required keys is valid
        self.assertTrue(validate_structured_output(data, []))
        # Empty dict with required keys is invalid
        self.assertFalse(validate_structured_output(data, ["name"]))


if __name__ == "__main__":
    unittest.main()
