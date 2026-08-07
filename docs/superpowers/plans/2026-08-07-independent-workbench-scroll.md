# Independent Workbench Scroll Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the desktop repository sidebar and workbench content scroll independently below the fixed top bar.

**Architecture:** Keep the existing two-column markup intact. CSS makes the desktop workbench shell exactly the available viewport height and gives each grid column its own vertical scroll area. The existing compact breakpoint resets this behavior to normal document scrolling.

**Tech Stack:** Python 3.11, FastAPI-rendered HTML, inline CSS, pytest.

## Global Constraints

- Change only the live WebUI stylesheet emitted by `harness/webui.py`; do not alter `design/webui-prototype.html`.
- Desktop behavior applies above the existing `980px` breakpoint.
- At `980px` and below, preserve the current single-column document-scrolling experience.
- Do not change routes, markup structure, JavaScript, or repository/task behavior.

---

### Task 1: Specify and implement independent scroll ownership

**Files:**

- Modify: `tests/test_service_cli_api.py` near `test_webui_repository_sidebar_preserves_spacing_between_controls_and_content`
- Modify: `harness/webui.py:611-613` and the existing `@media (max-width: 980px)` block near line 707

**Interfaces:**

- Consumes: `create_app(CoreService(...))` and `_endpoint(api, "/", "GET")` test helpers.
- Produces: a workbench stylesheet where `.dashboard-shell`, `.task-sidebar`, and `.main-view` have independent desktop scroll ownership, with the responsive override restoring document scrolling.

- [ ] **Step 1: Write the failing CSS contract test**

Add a test named `test_webui_workbench_uses_independent_desktop_scroll_regions`. Build an app with `CoreService(repo, llm=MockLLM([]))`, request `/`, and assert that its HTML contains all five exact CSS rules below.

    .dashboard-shell { display: grid; grid-template-columns: 320px minmax(0, 1fr); height: calc(100vh - 67px); overflow: hidden; }
    .task-sidebar { min-height: 0; overflow-y: auto;
    .main-view, .detail-shell { min-height: 0; overflow-y: auto; padding: 28px; }
    .dashboard-shell { height: auto; overflow: visible; }
    .task-sidebar, .main-view, .detail-shell { overflow: visible; }

- [ ] **Step 2: Run the focused test to verify it fails**

Run `pytest tests/test_service_cli_api.py::test_webui_workbench_uses_independent_desktop_scroll_regions -v`.

Expected: FAIL because the desktop shell uses `min-height` and neither column owns vertical overflow.

- [ ] **Step 3: Implement the minimal stylesheet change**

In `_style()` in `harness/webui.py`, replace the desktop shell/sidebar/main-view rules with these declarations while preserving unrelated rules:

    .dashboard-shell { display: grid; grid-template-columns: 320px minmax(0, 1fr); height: calc(100vh - 67px); overflow: hidden; }
    .task-sidebar { min-height: 0; overflow-y: auto; border-right: 1px solid var(--line); padding: 24px 18px; background: rgba(255,253,247,.62); }
    .main-view, .detail-shell { min-height: 0; overflow-y: auto; padding: 28px; }

Inside the existing `@media (max-width: 980px)` block, add:

    .dashboard-shell { height: auto; overflow: visible; }
    .task-sidebar, .main-view, .detail-shell { overflow: visible; }

- [ ] **Step 4: Run the focused test to verify it passes**

Run `pytest tests/test_service_cli_api.py::test_webui_workbench_uses_independent_desktop_scroll_regions -v`.

Expected: PASS.

- [ ] **Step 5: Run affected WebUI tests**

Run `pytest tests/test_service_cli_api.py -v`.

Expected: PASS.

- [ ] **Step 6: Commit**

Run `git add harness/webui.py tests/test_service_cli_api.py`, then `git commit -m "fix: separate workbench scroll regions"`.

### Task 2: Verify the repository-wide result

**Files:**

- Verify: `harness/webui.py`
- Verify: `tests/test_service_cli_api.py`

**Interfaces:**

- Consumes: the independent-scroll CSS contract added in Task 1.
- Produces: evidence that the UI change does not regress the project test suite.

- [ ] **Step 1: Run the full test suite**

Run `pytest -v`.

Expected: PASS with no failed tests.

- [ ] **Step 2: Inspect the final diff**

Run `git diff HEAD~1 --check` and `git status --short`.

Expected: no whitespace errors and no unintended modified files.
