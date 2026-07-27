# Default WebUI registry fix report

## Root cause

`create_app()` passed `None` to `include_webui()` unless its caller supplied a
registry explicitly. The WebUI rendered repository controls but the select
route rejected requests because no registry was configured.

## RED

Command:

```powershell
& 'C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_service_cli_api.py::test_default_app_registers_its_repository_and_can_select_it -q -p no:cacheprovider
```

Result: failed with `AttributeError: 'State' object has no attribute
'repository_registry'`.

## GREEN

The default application now creates an application-level registry in
`APPDATA/harness` (or `~/.config/harness` when `APPDATA` is absent), registers
the core repository, stores the registry on application state, and passes the
same instance to the WebUI.

The focused command above passed: `1 passed`.

## Review follow-up

The default-app regression now submits a real ASGI `POST` to
`/ui/repositories/{id}/select` and asserts the un-followed response status is
`303`. To prove the route assertion detects the original integration failure,
the WebUI registry argument was temporarily removed: the test then failed with
`assert 400 == 303`. Restoring the registry argument made the focused default
and explicit-registry tests pass: `2 passed`.

The explicit-registry coverage also asserts that
`api.state.repository_registry is registry`.
