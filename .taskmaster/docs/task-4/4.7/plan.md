# Implementation plan: Subtask 4.7 — Live Integration Tests and Final Exports

## Goal

Complete Task 4 (LLM Integration Framework) by adding live integration tests with real API calls to OpenAI and Anthropic. Verify that all framework components are properly exported and documented. This is the final subtask of Task 4.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| Live integration tests with real API calls | Load testing or performance benchmarks |
| Environment variable configuration for test models | Automated retry logic (defer to production code) |
| Lightweight model defaults (cost-effective) | Streaming response tests (streaming not in MVP) |
| `.env.example` with test model configuration | Fine-tuned or custom model testing |
| Documentation for running live tests | Token usage tracking/monitoring (future) |
| Verification of all exports from `core/__init__.py` | Embeddings or vector search tests |
| Cross-provider comparison tests | Multi-modal tests (images, audio) |

---

## Dependencies

- **Task 4.1** — LlmProvider base, OpenAiProvider (done)
- **Task 4.2** — ClaudeProvider (done)
- **Task 4.3** — ToolRegistry (done)
- **Task 4.4** — Structured output parsing (done)
- **Task 4.5** — Prompt utilities (done)
- **Task 4.6** — Conversation memory (done)
- **External:** Active OpenAI and Anthropic API keys (optional, tests skip if missing)

---

## Current Status

✅ **Unit tests:** All components have mocked unit tests (394 tests passing)
✅ **Exports:** All LLM framework components exported from `core/__init__.py`
❌ **Live tests:** Missing - need real API integration tests
❌ **Test model configuration:** Missing - need `.env.example` with test model defaults

---

## Files to Create / Modify

- **Modify:** `tests/unit/test_llm_framework.py` — Add `TestLiveOpenAiProvider`, `TestLiveClaudeProvider`, `TestLiveProviderComparison`
- **Modify:** `tests/unit/test_memory.py` — Add `TestLiveMemoryWithProvider`
- **Create:** `.env.example` — Environment variable template with API keys and test model configuration
- **Modify:** `README.md` or create `docs/TESTING.md` — Documentation for running live tests
- **Verify:** `core/__init__.py` — Ensure all LLM framework exports are present

---

## Test Models (Cost Optimization)

### Recommended Models for Live Tests

| Provider | Test Model | Production Model | Cost Savings |
|----------|-----------|------------------|--------------|
| OpenAI | `gpt-4o-mini` | `gpt-4o` | **17x cheaper** |
| Anthropic | `claude-haiku-4-5-20251001` | `claude-sonnet-4-5` | **4x cheaper** |

### Cost Analysis

**With lightweight test models:**
- ~20 live tests × 500 tokens avg = 10,000 tokens
- OpenAI (gpt-4o-mini): $0.15/$0.60 per 1M tokens → ~$0.0015 per run
- Anthropic (haiku): $0.80/$4.00 per 1M tokens → ~$0.008 per run
- **Total: ~$0.01 per full test run**

**With production models:**
- Same 10,000 tokens
- OpenAI (gpt-4o): $2.50/$10.00 per 1M tokens → ~$0.025 per run
- Anthropic (sonnet): $3.00/$15.00 per 1M tokens → ~$0.03 per run
- **Total: ~$0.055 per full test run**

**Using lightweight models reduces test costs by 5-6x while still validating integration.**

---

## Implementation Breakdown

### 1. Environment Configuration

Create `.env.example`:

```bash
# =============================================================================
# Zenet MVP 0.1 - Environment Configuration
# =============================================================================

# LLM API Keys (required for live integration tests)
# Obtain keys from:
# - OpenAI: https://platform.openai.com/api-keys
# - Anthropic: https://console.anthropic.com/account/keys
OPENAI_API_KEY=sk-your-openai-key-here
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here

# Test Models (optional - defaults to lightweight models)
# Live integration tests use these models to validate the framework works.
# Defaults are chosen for cost-effectiveness (~$0.01 per test run).
# Override to test with production models when needed.

# OpenAI test model (default: gpt-4o-mini)
# Cost: $0.15 input / $0.60 output per 1M tokens
# Alternative production models:
#   - gpt-4o: $2.50 / $10.00 per 1M tokens (17x more expensive)
#   - gpt-4-turbo: $10.00 / $30.00 per 1M tokens
TEST_OPENAI_MODEL=gpt-4o-mini

# Anthropic test model (default: claude-haiku-4-5-20251001)
# Cost: $0.80 input / $4.00 output per 1M tokens
# Alternative production models:
#   - claude-sonnet-4-5: $3.00 / $15.00 per 1M tokens (4x more expensive)
#   - claude-sonnet-4-6: Similar pricing to 4-5
#   - claude-opus-4-6: Most expensive, highest quality
TEST_ANTHROPIC_MODEL=claude-haiku-4-5-20251001
```

**Design decision:** Use environment variables (not hardcoded models) for:
- **Flexibility:** Easy to override for different environments (dev/CI/prod)
- **Consistency:** Same pattern as API keys
- **Maintainability:** Model name updates don't require code changes
- **CI/CD friendly:** Different pipelines can use different models
- **Documentation:** `.env.example` serves as self-documenting configuration

---

### 2. Live OpenAI Provider Tests

Add to `tests/unit/test_llm_framework.py`:

```python
class TestLiveOpenAiProvider(unittest.TestCase):
    """
    Live integration tests with real OpenAI API.

    These tests make REAL API calls to OpenAI. They are skipped if
    OPENAI_API_KEY is not set in the environment.

    Model: Controlled by TEST_OPENAI_MODEL env var (default: gpt-4o-mini).
    Cost: ~$0.005 per full test run with default model.

    Override model for one-time testing:
        TEST_OPENAI_MODEL=gpt-4o pytest tests/unit/ -k LiveOpenAi
    """

    def setUp(self):
        """Set up provider with test model from environment."""
        if os.getenv("OPENAI_API_KEY"):
            # Default to mini for cost savings, allow override
            test_model = os.getenv("TEST_OPENAI_MODEL", "gpt-4o-mini")
            self.provider = OpenAiProvider(model_name=test_model)

    @unittest.skipIf(not os.getenv("OPENAI_API_KEY"), "No OpenAI API key")
    def test_live_generate_simple_prompt(self):
        """
        Verify OpenAiProvider can make a real API call and return a response.

        This test makes ONE real API call to OpenAI.
        Expected cost: ~$0.0002 with gpt-4o-mini.
        """
        response = self.provider.generate(
            "What is 2+2? Answer with just the number.",
            temperature=0  # Deterministic
        )

        # Assertions (robust, non-deterministic friendly)
        self.assertIsNotNone(response)
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 0)
        self.assertIn("4", response)

    @unittest.skipIf(not os.getenv("OPENAI_API_KEY"), "No OpenAI API key")
    def test_live_generate_with_system(self):
        """
        Verify system message is properly injected into OpenAI API call.

        OpenAI expects system as a message with role="system".
        """
        response = self.provider.generate(
            "What is 5+3?",
            system="You are a helpful math tutor. Always explain your answers.",
            temperature=0
        )

        self.assertIsNotNone(response)
        self.assertIn("8", response)
        # System prompt should make response more verbose/explanatory
        self.assertGreater(len(response), 5)

    @unittest.skipIf(not os.getenv("OPENAI_API_KEY"), "No OpenAI API key")
    def test_live_generate_structured_output(self):
        """
        Verify JSON mode (structured_output=True) works with real API.

        OpenAI uses response_format={"type": "json_object"} for JSON mode.
        """
        prompt = (
            "Return a JSON object with these exact keys: "
            "'name' (set to 'test'), 'value' (set to 42), 'active' (set to true)."
        )

        response = self.provider.generate(
            prompt,
            structured_output=True,
            temperature=0
        )

        # Parse and validate
        data = parse_structured_output(response)
        self.assertIsInstance(data, dict)
        self.assertEqual(data.get("name"), "test")
        self.assertEqual(data.get("value"), 42)
        self.assertEqual(data.get("active"), True)

    @unittest.skipIf(not os.getenv("OPENAI_API_KEY"), "No OpenAI API key")
    def test_live_generate_with_tools(self):
        """
        Verify tool calling (function calling) works with real API.

        Tests that OpenAI properly receives and invokes tools.
        """
        # Simple calculator tool
        registry = ToolRegistry()

        def add(a: int, b: int) -> int:
            return a + b

        registry.register(
            "add",
            add,
            description="Add two numbers",
            parameters_schema={
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"}
                },
                "required": ["a", "b"]
            }
        )

        response = self.provider.generate(
            "Use the add tool to calculate 10 + 15",
            tools=registry.to_openai_tools(),
            temperature=0
        )

        # Response should mention tool usage or the result
        self.assertIsNotNone(response)
        # Note: Actual tool execution is up to the caller;
        # we're just verifying the API accepts tools

    @unittest.skipIf(not os.getenv("OPENAI_API_KEY"), "No OpenAI API key")
    def test_live_multi_turn_with_messages(self):
        """
        Verify multi-turn conversation with messages parameter.

        Tests that the provider correctly handles the messages list
        for context preservation.
        """
        messages = [
            {"role": "user", "content": "My name is Alice."},
            {"role": "assistant", "content": "Nice to meet you, Alice!"},
            {"role": "user", "content": "What is my name?"}
        ]

        response = self.provider.generate(
            prompt=None,  # Not used when messages provided
            messages=messages,
            temperature=0
        )

        # Should remember name from earlier message
        self.assertIn("Alice", response)
```

---

### 3. Live Claude Provider Tests

Add to `tests/unit/test_llm_framework.py`:

```python
class TestLiveClaudeProvider(unittest.TestCase):
    """
    Live integration tests with real Anthropic API.

    These tests make REAL API calls to Anthropic. They are skipped if
    ANTHROPIC_API_KEY is not set in the environment.

    Model: Controlled by TEST_ANTHROPIC_MODEL env var (default: claude-haiku-4-5-20251001).
    Cost: ~$0.008 per full test run with default model.

    Override model for one-time testing:
        TEST_ANTHROPIC_MODEL=claude-sonnet-4-5 pytest tests/unit/ -k LiveClaude
    """

    def setUp(self):
        """Set up provider with test model from environment."""
        if os.getenv("ANTHROPIC_API_KEY"):
            test_model = os.getenv("TEST_ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
            self.provider = ClaudeProvider(model_name=test_model)

    @unittest.skipIf(not os.getenv("ANTHROPIC_API_KEY"), "No Anthropic API key")
    def test_live_generate_simple_prompt(self):
        """
        Verify ClaudeProvider can make a real API call and return a response.

        This test makes ONE real API call to Anthropic.
        Expected cost: ~$0.0004 with claude-haiku.
        """
        response = self.provider.generate(
            "What is 2+2? Answer with just the number.",
            temperature=0
        )

        self.assertIsNotNone(response)
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 0)
        self.assertIn("4", response)

    @unittest.skipIf(not os.getenv("ANTHROPIC_API_KEY"), "No Anthropic API key")
    def test_live_generate_with_system(self):
        """
        Verify system message is properly passed to Anthropic API.

        Anthropic expects system as a dedicated 'system' parameter,
        not injected into messages list.
        """
        response = self.provider.generate(
            "What is 5+3?",
            system="You are a helpful math tutor. Always explain your answers.",
            temperature=0
        )

        self.assertIsNotNone(response)
        self.assertIn("8", response)
        self.assertGreater(len(response), 5)

    @unittest.skipIf(not os.getenv("ANTHROPIC_API_KEY"), "No Anthropic API key")
    def test_live_generate_structured_output(self):
        """
        Verify JSON instruction works with real Anthropic API.

        Anthropic doesn't have native JSON mode, so structured_output=True
        appends JSON instruction to the system prompt.
        """
        prompt = (
            "Return a JSON object with these exact keys: "
            "'name' (set to 'test'), 'value' (set to 42), 'active' (set to true)."
        )

        response = self.provider.generate(
            prompt,
            structured_output=True,
            temperature=0
        )

        # Parse and validate
        data = parse_structured_output(response)
        self.assertIsInstance(data, dict)
        self.assertEqual(data.get("name"), "test")
        self.assertEqual(data.get("value"), 42)
        self.assertEqual(data.get("active"), True)

    @unittest.skipIf(not os.getenv("ANTHROPIC_API_KEY"), "No Anthropic API key")
    def test_live_generate_with_tools(self):
        """
        Verify tool use works with real Anthropic API.

        Anthropic has its own tool format (different from OpenAI).
        """
        registry = ToolRegistry()

        def add(a: int, b: int) -> int:
            return a + b

        registry.register(
            "add",
            add,
            description="Add two numbers",
            parameters_schema={
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"}
                },
                "required": ["a", "b"]
            }
        )

        response = self.provider.generate(
            "Use the add tool to calculate 10 + 15",
            tools=registry.to_anthropic_tools(),
            temperature=0
        )

        self.assertIsNotNone(response)

    @unittest.skipIf(not os.getenv("ANTHROPIC_API_KEY"), "No Anthropic API key")
    def test_live_multi_turn_with_messages(self):
        """
        Verify multi-turn conversation with messages parameter.
        """
        messages = [
            {"role": "user", "content": "My name is Alice."},
            {"role": "assistant", "content": "Nice to meet you, Alice!"},
            {"role": "user", "content": "What is my name?"}
        ]

        response = self.provider.generate(
            prompt=None,
            messages=messages,
            temperature=0
        )

        self.assertIn("Alice", response)
```

---

### 4. Cross-Provider Comparison Tests

Add to `tests/unit/test_llm_framework.py`:

```python
class TestLiveProviderComparison(unittest.TestCase):
    """
    Cross-provider tests comparing OpenAI and Claude behavior.

    These tests require BOTH API keys. They verify that both providers
    handle the same inputs correctly, validating provider abstraction.

    Cost: ~$0.001 per test with lightweight models.
    """

    def setUp(self):
        """Set up both providers with test models."""
        if os.getenv("OPENAI_API_KEY"):
            openai_model = os.getenv("TEST_OPENAI_MODEL", "gpt-4o-mini")
            self.openai = OpenAiProvider(model_name=openai_model)

        if os.getenv("ANTHROPIC_API_KEY"):
            claude_model = os.getenv("TEST_ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
            self.claude = ClaudeProvider(model_name=claude_model)

    @unittest.skipIf(
        not (os.getenv("OPENAI_API_KEY") and os.getenv("ANTHROPIC_API_KEY")),
        "Need both API keys"
    )
    def test_live_same_prompt_both_providers(self):
        """
        Verify both providers can handle the same simple prompt.

        This validates the unified LlmProvider interface.
        """
        prompt = "What is 2+2? Answer with just the number."

        openai_response = self.openai.generate(prompt, temperature=0)
        claude_response = self.claude.generate(prompt, temperature=0)

        # Both should return valid responses
        self.assertIsNotNone(openai_response)
        self.assertIsNotNone(claude_response)

        # Both should contain "4"
        self.assertIn("4", openai_response)
        self.assertIn("4", claude_response)

    @unittest.skipIf(
        not (os.getenv("OPENAI_API_KEY") and os.getenv("ANTHROPIC_API_KEY")),
        "Need both API keys"
    )
    def test_live_structured_output_both_providers(self):
        """
        Verify structured output parity across providers.

        OpenAI uses response_format, Claude uses JSON instruction.
        Both should produce valid JSON.
        """
        prompt = "Return a JSON object with key 'result' set to 42."

        openai_response = self.openai.generate(
            prompt,
            structured_output=True,
            temperature=0
        )
        claude_response = self.claude.generate(
            prompt,
            structured_output=True,
            temperature=0
        )

        # Both should return parseable JSON
        openai_data = parse_structured_output(openai_response)
        claude_data = parse_structured_output(claude_response)

        self.assertIsInstance(openai_data, dict)
        self.assertIsInstance(claude_data, dict)

        self.assertEqual(openai_data.get("result"), 42)
        self.assertEqual(claude_data.get("result"), 42)
```

---

### 5. Memory Integration Test

Add to `tests/unit/test_memory.py`:

```python
class TestLiveMemoryWithProvider(unittest.TestCase):
    """
    Live test of ConversationMemory with a real LLM provider.

    Verifies that memory correctly preserves context across multiple
    turns when used with actual API calls.

    Uses OpenAI by default (cheaper than Claude for this test).
    Cost: ~$0.001 per test with gpt-4o-mini.
    """

    def setUp(self):
        """Set up provider and memory for live tests."""
        if os.getenv("OPENAI_API_KEY"):
            test_model = os.getenv("TEST_OPENAI_MODEL", "gpt-4o-mini")
            self.provider = OpenAiProvider(model_name=test_model)
            self.memory = ConversationMemory(max_turns=10)

    @unittest.skipIf(not os.getenv("OPENAI_API_KEY"), "No OpenAI API key")
    def test_live_memory_context_preservation(self):
        """
        Verify memory preserves context across multiple API calls.

        Turn 1: User provides information
        Turn 2: User asks question requiring context from Turn 1

        Expected: Provider uses memory to answer correctly.
        """
        # Turn 1: Provide information
        user_msg_1 = "My favorite color is blue."
        self.memory.add_user(user_msg_1)

        response_1 = self.provider.generate(
            user_msg_1,
            messages=self.memory.get_messages(),
            temperature=0
        )
        self.memory.add_assistant(response_1)

        # Turn 2: Ask question requiring context
        user_msg_2 = "What is my favorite color?"
        self.memory.add_user(user_msg_2)

        response_2 = self.provider.generate(
            prompt=None,  # Not used when messages provided
            messages=self.memory.get_messages(),
            temperature=0
        )
        self.memory.add_assistant(response_2)

        # Verify context was preserved
        self.assertIn("blue", response_2.lower())

        # Verify memory contains all messages
        messages = self.memory.get_messages()
        self.assertEqual(len(messages), 4)  # 2 user + 2 assistant
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[2]["role"], "user")
        self.assertEqual(messages[3]["role"], "assistant")
```

---

### 6. Documentation

#### **Update README.md or create docs/TESTING.md:**

```markdown
## Running Tests

### Unit Tests (Mocked, No API Calls)

Unit tests use mocked API responses and run quickly without requiring API keys:

```bash
# Run all unit tests (skips live tests automatically)
python -m pytest tests/unit/ -v

# Run specific test file
python -m pytest tests/unit/test_llm_framework.py -v
```

### Live Integration Tests (Real API Calls)

Live tests make real API calls to OpenAI and Anthropic. They are **optional** and require:
1. API keys in your `.env` file
2. Active internet connection
3. Small cost per run (~$0.01 with default lightweight models)

#### Setup

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Add your API keys to `.env`:
   ```bash
   OPENAI_API_KEY=sk-your-key-here
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```

3. (Optional) Override test models in `.env`:
   ```bash
   # Defaults are lightweight models (recommended)
   TEST_OPENAI_MODEL=gpt-4o-mini
   TEST_ANTHROPIC_MODEL=claude-haiku-4-5-20251001
   ```

#### Running Live Tests

```bash
# Run only live tests (requires API keys)
python -m pytest tests/unit/ -k Live -v

# Run all tests (live tests run if API keys present, skip otherwise)
python -m pytest tests/unit/ -v

# Run OpenAI live tests only
python -m pytest tests/unit/ -k LiveOpenAi -v

# Run Claude live tests only
python -m pytest tests/unit/ -k LiveClaude -v

# Skip live tests explicitly
python -m pytest tests/unit/ -k "not Live" -v
```

#### One-Time Model Override

Test with production models without editing `.env`:

```bash
# Test OpenAI with gpt-4o (production model)
TEST_OPENAI_MODEL=gpt-4o python -m pytest tests/unit/ -k LiveOpenAi -v

# Test Claude with sonnet (production model)
TEST_ANTHROPIC_MODEL=claude-sonnet-4-5 python -m pytest tests/unit/ -k LiveClaude -v
```

#### Cost Considerations

**With default lightweight models:**
- Cost per full live test run: ~$0.01
- Safe to run frequently during development

**With production models:**
- Cost per full live test run: ~$0.05
- Only use when validating production parity

#### CI/CD Integration

GitHub Actions example (`.github/workflows/test.yml`):

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          pip install uv
          uv sync

      - name: Run unit tests (no API calls)
        run: python -m pytest tests/unit/ -k "not Live" -v

      - name: Run live tests (optional)
        if: ${{ secrets.OPENAI_API_KEY && secrets.ANTHROPIC_API_KEY }}
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          TEST_OPENAI_MODEL: gpt-4o-mini
          TEST_ANTHROPIC_MODEL: claude-haiku-4-5-20251001
        run: python -m pytest tests/unit/ -k Live -v
```
```

---

### 7. Verify Exports

Verify that `core/__init__.py` exports all LLM framework components:

```python
# From core/ai/providers.py
from core import LlmProvider, OpenAiProvider, ClaudeProvider, ToolRegistry

# From core/ai/memory.py
from core import ConversationMemory

# From core/ai/utils.py
from core import parse_structured_output, validate_structured_output

# From core/ai/prompts.py
from core import (
    PromptTemplate,
    format_system_prompt,
    format_user_prompt,
    INGREDIENT_EXTRACTION_PROMPT,
    INVENTORY_ITEM_SUGGESTION_PROMPT,
    RECIPE_CLASSIFICATION_PROMPT,
)
```

**Verification:** All imports should work without errors after restructuring (already done).

---

## Test Strategy

### Test Categorization

| Category | Count | API Calls | Cost | Skip Condition |
|----------|-------|-----------|------|----------------|
| OpenAI live tests | 5 | 5 | ~$0.005 | No OPENAI_API_KEY |
| Claude live tests | 5 | 5 | ~$0.008 | No ANTHROPIC_API_KEY |
| Cross-provider tests | 2 | 4 | ~$0.002 | No API keys for both |
| Memory integration | 1 | 2 | ~$0.001 | No OPENAI_API_KEY |
| **Total** | **13** | **16** | **~$0.016** | - |

### Robust Assertions for Non-Deterministic Responses

Live tests must handle non-deterministic LLM responses:

✅ **Good assertions:**
- `self.assertIsNotNone(response)`
- `self.assertGreater(len(response), 0)`
- `self.assertIn("keyword", response.lower())`
- `self.assertIsInstance(data, dict)` (after parsing)

❌ **Bad assertions:**
- `self.assertEqual(response, "exact text")` — LLMs vary responses
- `self.assertRegex(response, r"^The answer is 4\.$")` — Too strict

### Test Isolation

- Each test is independent (no shared state)
- setUp creates fresh provider/memory instances
- Tests can run in any order
- No test depends on another test's side effects

---

## Edge Cases

| Case | Behavior |
|------|----------|
| API key missing | Tests skipped with clear message |
| API key invalid | Test fails with API error (expected) |
| Network failure | Test fails with connection error (expected) |
| Rate limit hit | Test fails with rate limit error (expected) |
| TEST_*_MODEL env var missing | Uses default lightweight model |
| TEST_*_MODEL invalid | Test fails with API error (expected) |
| Both API keys missing | All live tests skipped |
| Only one API key present | Only that provider's tests run |
| Cross-provider test with one key | Skipped (needs both) |

**Note:** API errors, rate limits, and network failures are expected and acceptable in live tests. We're testing integration, not API reliability.

---

## Deliverable Checklist

### Environment Configuration
- [ ] Create `.env.example` with API keys and test model configuration
- [ ] Verify `.env` is in `.gitignore` (should already be)
- [ ] Document test models in `.env.example` comments

### Live Tests - OpenAI (test_llm_framework.py)
- [ ] Create `TestLiveOpenAiProvider` class
- [ ] Test: simple prompt generation
- [ ] Test: generation with system message
- [ ] Test: structured output (JSON mode)
- [ ] Test: tool calling (function calling)
- [ ] Test: multi-turn with messages parameter

### Live Tests - Claude (test_llm_framework.py)
- [ ] Create `TestLiveClaudeProvider` class
- [ ] Test: simple prompt generation
- [ ] Test: generation with system message
- [ ] Test: structured output (JSON instruction)
- [ ] Test: tool use
- [ ] Test: multi-turn with messages parameter

### Live Tests - Cross-Provider (test_llm_framework.py)
- [ ] Create `TestLiveProviderComparison` class
- [ ] Test: same prompt to both providers
- [ ] Test: structured output parity

### Live Tests - Memory (test_memory.py)
- [ ] Create `TestLiveMemoryWithProvider` class
- [ ] Test: context preservation across turns

### Documentation
- [ ] Add "Running Tests" section to README.md or docs/TESTING.md
- [ ] Document live test setup and execution
- [ ] Document cost considerations
- [ ] Document one-time model override
- [ ] Add CI/CD integration example

### Verification
- [ ] Verify all LLM framework exports in `core/__init__.py`
- [ ] Run unit tests: `python -m pytest tests/unit/ -k "not Live" -v` (should pass)
- [ ] Run live tests if API keys available: `python -m pytest tests/unit/ -k Live -v`
- [ ] Verify tests skip gracefully when API keys missing

---

## Notes

- **API keys:** Read from environment, never commit to repo. `.env` must remain in `.gitignore`.
- **Cost control:** Lightweight models by default (gpt-4o-mini, claude-haiku) reduce cost by 5-6x.
- **Test isolation:** Each test is independent; no shared state between tests.
- **Non-deterministic responses:** Assertions must be robust (check for patterns/keywords, not exact text).
- **Skip behavior:** Tests skip gracefully with clear messages when API keys are missing.
- **Environment variables preferred over hardcoding:** Allows flexibility without code changes.
- **Live tests are optional:** Unit tests (mocked) provide core validation; live tests verify real integration.
- **CI/CD:** Live tests can be optional in CI (run only if secrets are configured).

---

## Time Estimate

- **Environment config (.env.example):** 15 minutes
- **Live OpenAI tests:** 45 minutes (5 tests)
- **Live Claude tests:** 45 minutes (5 tests)
- **Cross-provider tests:** 20 minutes (2 tests)
- **Memory integration test:** 15 minutes (1 test)
- **Documentation:** 30 minutes (README/TESTING.md updates)
- **Testing and refinement:** 30 minutes
- **Total:** **3-3.5 hours**

---

## Success Criteria

✅ **Task 4 complete when:**
1. All 13 live tests implemented and documented
2. `.env.example` created with test model configuration
3. Tests skip gracefully when API keys missing
4. Tests pass when API keys are present
5. Documentation explains how to run live tests
6. Cost per test run is ~$0.01 with default models
7. All LLM framework components exported and verified

**Upon completion, Task 4 (LLM Integration Framework) is 100% done and ready for Task 5 (Agent Framework)!**
