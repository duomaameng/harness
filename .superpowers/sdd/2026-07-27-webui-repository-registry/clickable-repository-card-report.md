# Clickable repository card report

## RED

Added `test_webui_repository_card_selects_without_a_select_button` to
`tests/test_service_cli_api.py`. It renders a registry with an available and a
current repository, then verifies that the HTML has no `Select` button, that
the available repository's card posts to its `/select` route, that the current
repository has no select route, and that rename/delete routes remain present.

Command:

```powershell
& 'C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_service_cli_api.py -k repository_card_selects_without_a_select_button -q -p no:cacheprovider
```

Observed result: 1 failed as expected because the rendered HTML still
contained `>Select</button>`.

## GREEN

Changed `harness/webui.py` so an available repository's name/path area is a
standalone POST form whose button submits to
`/ui/repositories/{id}/select`. The current repository displays the same
summary without a select form. Rename and delete remain sibling forms, so no
forms are nested and their controls do not submit the selection form.

Re-ran the focused command above. Observed result: `1 passed, 38 deselected`.

No full test suite was run.
