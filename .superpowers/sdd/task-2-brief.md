### Task 2: Task Profiler And Validation Discovery Hints

**Parallel:** Yes, after Task 1.

**Depends On:** Task 1.

**Goal:** Classify user requests into task profiles with likely modules, symbols, validation requirements, and out-of-scope flags.

**Files:**
- Create: `harness/profiler.py`
- Create: `tests/test_profiler.py`
- Modify: `harness/domain.py`

**Implementation Points:**
- Add `TaskProfile` with task type, keywords, symbols, likely modules, validation requirements, `out_of_scope`, and `decomposition_reason`.
- Detect cross-repository, external deployment, and large architecture rewrite requests as out of scope.
- Infer validation requirements from request wording such as tests, lint, typecheck, build, Docker, CLI, API, WebUI, guardrail, memory, and report.
- Keep logic deterministic with keyword and path-like signal extraction.

**First Failing Test:**
- Write `tests/test_profiler.py::test_profiler_marks_cross_repo_deployment_out_of_scope`.
- It should pass a request mentioning two repositories and production deployment, then assert `out_of_scope is True` and the decomposition reason names both cross-repository work and deployment.
- Initial expected failure: `TaskProfiler` does not exist.

**Validation Commands:**
- `python -m pytest tests/test_profiler.py::test_profiler_marks_cross_repo_deployment_out_of_scope -q`
- `python -m pytest tests/test_profiler.py -q`

