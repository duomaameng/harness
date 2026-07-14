### Task 6: Guardrails And Approval Classification

**Parallel:** No.

**Depends On:** Tasks 1, 4, 5.

**Goal:** Evaluate every parsed action for repository boundary safety, sensitive file access, risky writes, dangerous commands, and approval requirements.

**Files:**
- Create: `harness/guardrails.py`
- Create: `tests/test_guardrails.py`
- Modify: `harness/domain.py`

**Implementation Points:**
- Canonicalize all paths and deny access outside repository root.
- Deny or require approval for `.env`, key files, credential-like paths, deletion, critical config overwrites, network, publish, install, and git history commands.
- Allow known validation commands such as `python -m pytest`, `pytest`, `ruff check`, `mypy`, and `python -m build` when configured or discovered.
- Return `allow`, `deny`, or `require_approval` with risk level and reason.

**First Failing Test:**
- Write `tests/test_guardrails.py::test_path_traversal_read_is_denied_before_dispatch`.
- It should build a `read_file` action for `../secret.txt`, evaluate it against a temp repo root, and assert status is `deny` with a reason mentioning repository root.
- Initial expected failure: `Guardrail` does not exist.

**Validation Commands:**
- `python -m pytest tests/test_guardrails.py::test_path_traversal_read_is_denied_before_dispatch -q`
- `python -m pytest tests/test_guardrails.py -q`


