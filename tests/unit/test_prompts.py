"""
Unit tests for prompt templating utilities.

Tests PromptTemplate dataclass, helper functions, and pre-built templates.
"""

import unittest

from core.ai.prompts import (
    INGREDIENT_EXTRACTION_PROMPT,
    INVENTORY_ITEM_SUGGESTION_PROMPT,
    PromptTemplate,
    RECIPE_CLASSIFICATION_PROMPT,
    format_system_prompt,
    format_user_prompt,
)


class TestPromptTemplate(unittest.TestCase):
    """Tests for PromptTemplate dataclass."""

    def test_instantiation(self):
        """Test creating a PromptTemplate."""
        template = PromptTemplate(
            name="test_template",
            system="You are a test assistant.",
            user_template="Process this: {item}",
        )
        self.assertEqual(template.name, "test_template")
        self.assertEqual(template.system, "You are a test assistant.")
        self.assertEqual(template.user_template, "Process this: {item}")

    def test_render_with_single_variable(self):
        """Test rendering template with one variable."""
        template = PromptTemplate(
            name="test", system="System prompt", user_template="Analyze {item}"
        )
        system, user = template.render(item="pasta")
        self.assertEqual(system, "System prompt")
        self.assertEqual(user, "Analyze pasta")

    def test_render_with_multiple_variables(self):
        """Test rendering template with multiple variables."""
        template = PromptTemplate(
            name="test",
            system="System",
            user_template="Extract {field1} and {field2} from {source}",
        )
        system, user = template.render(field1="name", field2="quantity", source="recipe")
        self.assertEqual(user, "Extract name and quantity from recipe")

    def test_render_with_no_variables(self):
        """Test rendering template without variables."""
        template = PromptTemplate(
            name="test", system="System", user_template="Static prompt"
        )
        system, user = template.render()
        self.assertEqual(user, "Static prompt")

    def test_render_with_extra_kwargs(self):
        """Test that extra kwargs are ignored."""
        template = PromptTemplate(
            name="test", system="System", user_template="Process {item}"
        )
        system, user = template.render(item="data", extra="ignored")
        self.assertEqual(user, "Process data")

    def test_render_missing_variable_raises_error(self):
        """Test that missing variable raises KeyError."""
        template = PromptTemplate(
            name="test", system="System", user_template="Process {item}"
        )
        with self.assertRaises(KeyError):
            template.render()

    def test_render_returns_tuple(self):
        """Test that render returns (system, user) tuple."""
        template = PromptTemplate(
            name="test", system="System", user_template="User {x}"
        )
        result = template.render(x="test")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_render_with_multiline_template(self):
        """Test rendering multiline user template."""
        template = PromptTemplate(
            name="test",
            system="System",
            user_template="""Line 1: {var1}
Line 2: {var2}
Line 3: static""",
        )
        system, user = template.render(var1="A", var2="B")
        self.assertIn("Line 1: A", user)
        self.assertIn("Line 2: B", user)
        self.assertIn("Line 3: static", user)

    def test_render_same_variable_multiple_times(self):
        """Test using same variable multiple times in template."""
        template = PromptTemplate(
            name="test",
            system="System",
            user_template="First {x}, second {x}, third {x}",
        )
        system, user = template.render(x="value")
        self.assertEqual(user, "First value, second value, third value")

    def test_render_with_empty_user_template(self):
        """Test rendering with empty user template."""
        template = PromptTemplate(name="test", system="System", user_template="")
        system, user = template.render()
        self.assertEqual(system, "System")
        self.assertEqual(user, "")

    def test_render_with_empty_system(self):
        """Test rendering with empty system prompt."""
        template = PromptTemplate(name="test", system="", user_template="User {x}")
        system, user = template.render(x="test")
        self.assertEqual(system, "")
        self.assertEqual(user, "User test")


class TestFormatSystemPrompt(unittest.TestCase):
    """Tests for format_system_prompt helper function."""

    def test_role_only(self):
        """Test formatting with role only."""
        result = format_system_prompt("recipe analyst")
        self.assertEqual(result, "You are a recipe analyst.")

    def test_role_with_context(self):
        """Test formatting with role and context."""
        result = format_system_prompt("recipe analyst", "for an Italian restaurant")
        self.assertEqual(result, "You are a recipe analyst for an Italian restaurant.")

    def test_context_none_same_as_no_context(self):
        """Test that context=None is same as no context."""
        result1 = format_system_prompt("chef", None)
        result2 = format_system_prompt("chef")
        self.assertEqual(result1, result2)
        self.assertEqual(result1, "You are a chef.")

    def test_empty_role(self):
        """Test with empty role string."""
        result = format_system_prompt("", "for testing")
        self.assertEqual(result, "You are a  for testing.")

    def test_complex_role_and_context(self):
        """Test with complex multi-word role and context."""
        result = format_system_prompt(
            "inventory management specialist",
            "helping organize supplies for a Mexican taqueria",
        )
        expected = "You are a inventory management specialist helping organize supplies for a Mexican taqueria."
        self.assertEqual(result, expected)

    def test_ends_with_period(self):
        """Test that result always ends with period."""
        result1 = format_system_prompt("analyst")
        result2 = format_system_prompt("analyst", "for restaurants")
        self.assertTrue(result1.endswith("."))
        self.assertTrue(result2.endswith("."))


class TestFormatUserPrompt(unittest.TestCase):
    """Tests for format_user_prompt helper function."""

    def test_single_variable(self):
        """Test formatting with single variable."""
        result = format_user_prompt("Extract from: {text}", text="recipe")
        self.assertEqual(result, "Extract from: recipe")

    def test_multiple_variables(self):
        """Test formatting with multiple variables."""
        result = format_user_prompt(
            "Process {item1} and {item2}", item1="eggs", item2="flour"
        )
        self.assertEqual(result, "Process eggs and flour")

    def test_no_variables(self):
        """Test formatting template with no variables."""
        result = format_user_prompt("Static text")
        self.assertEqual(result, "Static text")

    def test_missing_variable_raises_error(self):
        """Test that missing variable raises KeyError."""
        with self.assertRaises(KeyError):
            format_user_prompt("Extract {missing}")

    def test_extra_kwargs_ignored(self):
        """Test that extra kwargs are ignored."""
        result = format_user_prompt("Use {x}", x="value", extra="ignored")
        self.assertEqual(result, "Use value")

    def test_multiline_template(self):
        """Test multiline template formatting."""
        template = """Line 1: {a}
Line 2: {b}"""
        result = format_user_prompt(template, a="A", b="B")
        self.assertIn("Line 1: A", result)
        self.assertIn("Line 2: B", result)


class TestPreBuiltTemplates(unittest.TestCase):
    """Tests for pre-built prompt templates."""

    def test_ingredient_extraction_prompt_exists(self):
        """Test that INGREDIENT_EXTRACTION_PROMPT is defined."""
        self.assertIsInstance(INGREDIENT_EXTRACTION_PROMPT, PromptTemplate)
        self.assertEqual(INGREDIENT_EXTRACTION_PROMPT.name, "ingredient_extraction")

    def test_ingredient_extraction_prompt_has_system(self):
        """Test that ingredient extraction has non-empty system."""
        self.assertIsInstance(INGREDIENT_EXTRACTION_PROMPT.system, str)
        self.assertGreater(len(INGREDIENT_EXTRACTION_PROMPT.system), 0)

    def test_ingredient_extraction_prompt_has_user_template(self):
        """Test that ingredient extraction has user template."""
        self.assertIsInstance(INGREDIENT_EXTRACTION_PROMPT.user_template, str)
        self.assertGreater(len(INGREDIENT_EXTRACTION_PROMPT.user_template), 0)

    def test_ingredient_extraction_prompt_renders(self):
        """Test that ingredient extraction prompt renders successfully."""
        system, user = INGREDIENT_EXTRACTION_PROMPT.render(
            recipe_text="Pasta: 200g flour, 2 eggs"
        )
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)
        self.assertIn("Pasta: 200g flour, 2 eggs", user)

    def test_recipe_classification_prompt_exists(self):
        """Test that RECIPE_CLASSIFICATION_PROMPT is defined."""
        self.assertIsInstance(RECIPE_CLASSIFICATION_PROMPT, PromptTemplate)
        self.assertEqual(RECIPE_CLASSIFICATION_PROMPT.name, "recipe_classification")

    def test_recipe_classification_prompt_renders(self):
        """Test that recipe classification prompt renders successfully."""
        system, user = RECIPE_CLASSIFICATION_PROMPT.render(
            categories=["appetizers", "mains", "desserts"],
            recipe_name="Tiramisu",
            recipe_description="Italian dessert",
        )
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)
        self.assertIn("Tiramisu", user)
        self.assertIn("Italian dessert", user)

    def test_inventory_item_suggestion_prompt_exists(self):
        """Test that INVENTORY_ITEM_SUGGESTION_PROMPT is defined."""
        self.assertIsInstance(INVENTORY_ITEM_SUGGESTION_PROMPT, PromptTemplate)
        self.assertEqual(INVENTORY_ITEM_SUGGESTION_PROMPT.name, "inventory_item_suggestion")

    def test_inventory_item_suggestion_prompt_renders(self):
        """Test that inventory suggestion prompt renders successfully."""
        system, user = INVENTORY_ITEM_SUGGESTION_PROMPT.render(
            ingredient_name="eggs",
            recipe_name="Pasta Carbonara",
            families=["dairy", "proteins", "vegetables"],
        )
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)
        self.assertIn("eggs", user)
        self.assertIn("Pasta Carbonara", user)

    def test_all_templates_have_unique_names(self):
        """Test that all pre-built templates have unique names."""
        names = [
            INGREDIENT_EXTRACTION_PROMPT.name,
            RECIPE_CLASSIFICATION_PROMPT.name,
            INVENTORY_ITEM_SUGGESTION_PROMPT.name,
        ]
        self.assertEqual(len(names), len(set(names)), "Template names must be unique")

    def test_all_templates_use_format_system_prompt(self):
        """Test that all pre-built templates use format_system_prompt pattern."""
        # All should start with "You are a"
        for template in [
            INGREDIENT_EXTRACTION_PROMPT,
            RECIPE_CLASSIFICATION_PROMPT,
            INVENTORY_ITEM_SUGGESTION_PROMPT,
        ]:
            self.assertTrue(
                template.system.startswith("You are a"),
                f"{template.name} should use format_system_prompt pattern",
            )

    def test_templates_include_json_structure_examples(self):
        """Test that templates guide JSON output structure."""
        # Ingredient extraction should mention JSON
        self.assertIn("JSON", INGREDIENT_EXTRACTION_PROMPT.user_template)

        # Recipe classification should show JSON structure
        self.assertIn("JSON", RECIPE_CLASSIFICATION_PROMPT.user_template)
        self.assertIn("category", RECIPE_CLASSIFICATION_PROMPT.user_template)

        # Inventory suggestion should show JSON structure
        self.assertIn("JSON", INVENTORY_ITEM_SUGGESTION_PROMPT.user_template)


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests combining templates with other utilities."""

    def test_template_with_llm_provider_signature(self):
        """Test that template output matches LlmProvider.generate() signature."""
        template = PromptTemplate(
            name="test", system="System", user_template="User {x}"
        )
        system, user = template.render(x="test")

        # These should be usable as: provider.generate(user, system=system)
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)

    def test_custom_template_for_chat(self):
        """Test creating a custom chat template."""
        chat_template = PromptTemplate(
            name="restaurant_chat",
            system=format_system_prompt(
                "restaurant operations assistant", "helping manage inventory and recipes"
            ),
            user_template="{user_message}",
        )

        system, user = chat_template.render(user_message="How many fruits do I have?")

        self.assertIn("restaurant operations assistant", system)
        self.assertEqual(user, "How many fruits do I have?")

    def test_template_render_error_message_includes_variable_name(self):
        """Test that KeyError includes variable name."""
        template = PromptTemplate(
            name="test", system="System", user_template="Process {missing_var}"
        )

        try:
            template.render()
            self.fail("Should have raised KeyError")
        except KeyError as e:
            # Error should mention the missing variable
            self.assertIn("missing_var", str(e))


if __name__ == "__main__":
    unittest.main()
