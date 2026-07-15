# Task 9: Feedback Engine And Validation Loop Signals

## Goal

Discover validation commands, run configured validations, parse failures into structured feedback, and detect repeated unchanged failures.

## Files

- Create: `harness/feedback.py`
- Create: `tests/test_feedback.py`
- Modify: `harness/domain.py`

## Implementation Points

- Prefer configured validation commands and infer fallback commands from `pyproject.toml`, `package.json`, `Cargo.toml`, `pom.xml`, and common conventions.
- Parse pytest, lint, typecheck, build, schema validation, guardrail denial, approval rejection, timeout, and generic exit-code failures.
- Store category, summary, locations, and redacted raw excerpt.
- Compare consecutive failures by category and key location for early stop decisions.

## First Failing Test

- Write `tests/test_feedback.py::test_repeated_same_pytest_failure_stops_after_second_occurrence`.
- It should pass two feedback objects with category `assertion_failure` and the same file/test location, then assert the engine recommends early stop.
- Initial expected failure: `FeedbackEngine` does not exist.

## Validation Commands

- `python -m pytest tests/test_feedback.py::test_repeated_same_pytest_failure_stops_after_second_occurrence -q`
- `python -m pytest tests/test_feedback.py -q`

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
