# Task 1: Repository-card overflow menu and management dialogs

Read this file first. It is the complete requirement.

## Files

- Modify `tests/test_service_cli_api.py`
- Modify `harness/webui.py`
- Modify `PLAN.md`
- Modify `AGENT_LOG.md`

## Requirements

- Do not change `/ui/repositories/{repository_id}/rename` or `/ui/repositories/{repository_id}/delete` route behavior.
- Replace the visible repository rename input and Rename/Delete buttons with a labelled overflow menu on each repository card.
- Render exactly one rename dialog (`id="rename-repository-dialog"`) and one removal confirmation dialog (`id="delete-repository-dialog"`) in the page.
- Menu actions must have accessible labels. Clicking management controls must not activate card selection.
- The rename dialog must prefill and autofocus the current name; Escape cancels and Enter submits.
- The removal dialog must say: `Remove from workbench only. Local files are never deleted.`
- Keep the current JSON form submission behavior for repository mutations.
- Use TDD: write the focused failing test first, run it and record the expected failure, implement only what makes it pass, refactor, and re-run the focused test.
- Update `PLAN.md` and `AGENT_LOG.md` with this work and test evidence, then commit all task files.

## Required test

Add `test_webui_repository_card_uses_overflow_menu_and_management_dialogs` in `tests/test_service_cli_api.py`. It must render at least two registered repositories and assert the menu, accessible trigger, both dialogs, removal copy, and absence of the old visible rename form in the sidebar.

Run:

`python -m pytest tests/test_service_cli_api.py::test_webui_repository_card_uses_overflow_menu_and_management_dialogs -q -p no:cacheprovider`

## Global constraints

- Scope is only this repository-card management UI feature.
- Do not introduce dependencies.
