# Task 10: LLM Clients And Agent Runner Main Loop

## Goal

Implement the model abstraction, MockLLM, OpenAI-compatible client shell, and bounded Agent Runner lifecycle.

## Files

- Create: `harness/llm.py`
- Create: `harness/runner.py`
- Create: `tests/test_runner.py`
- Modify: `harness/storage.py`

## Implementation Points

- `LLMClient` only sends messages and returns model output.
- `MockLLM` returns a predefined sequence of structured action strings.
- OpenAI-compatible client accepts `base_url`, `model`, and API key but is not used by offline tests.
- `AgentRunner` creates model inputs from task, profile, context, prior actions, and feedback.
- Runner parses actions, applies guardrails, dispatches tools, runs validation, records audit events, respects approval wait state, and stops at success, repeated failure, or six repair rounds.

## First Failing Test

- Write `tests/test_runner.py::test_invalid_action_from_mock_llm_becomes_feedback_without_tool_execution`.
- It should configure MockLLM to return invalid JSON, run one loop, and assert schema feedback exists and no tool result exists.
- Initial expected failure: `AgentRunner` or `MockLLM` does not exist.

## Validation Commands

- `python -m pytest tests/test_runner.py::test_invalid_action_from_mock_llm_becomes_feedback_without_tool_execution -q`
- `python -m pytest tests/test_runner.py -q`

## Global Constraints

- Scope is single-repository feature development only.
- Core mechanisms must run with `MockLLM` without network access or API keys.
- LLM output must be structured JSON actions and must never execute tools directly.
- Every executable action passes schema validation and guardrail checks before dispatch.
- Context retrieval is code-driven first; LLM assistance may rank or explain only.
- Credentials are never hardcoded, committed, logged, stored in SQLite, stored in JSONL, shown in WebUI plaintext, or included in prompts.
- Default repair limit is six rounds.
- Stop early after two consecutive rounds with the same failure category and key location.
- `.harness/` and `.env` are local data or development fallback and must be ignored by Git.
- CI must include a job named `unit-test` that runs pytest and avoids real API keys.
- CI must build the Docker image.
