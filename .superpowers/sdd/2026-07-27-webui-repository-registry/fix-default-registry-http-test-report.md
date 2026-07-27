# Default registry HTTP regression-test fix

## Scope

Addressed only P1 from `review-default-registry-fix.md`. The production change in
commit `8d26223` remains unchanged.

## Test coverage

- `test_default_app_registers_its_repository_and_can_select_it` now dispatches an
  ASGI `POST` to `/ui/repositories/{repository_id}/select` and asserts the real
  `303` response plus `Location: /` without following the redirect.
- The focused ASGI helper uses `asyncio` because the bundled runtime does not have
  `httpx`, so FastAPI/Starlette `TestClient` is unavailable. It drives the full
  ASGI request/route/response path and rejects redirect following explicitly.
- `test_webui_repository_switches_task_service_and_isolates_tasks` asserts that an
  explicitly supplied `RepositoryRegistry` remains the exact instance exposed via
  `api.state.repository_registry`.

## Red/green evidence

With the `8d26223` registry initialization temporarily removed, the ASGI POST
regression test failed with `assert 400 == 303`. The production implementation was
then restored unchanged.

Final focused verification:

```text
python.exe -m pytest \
  tests/test_service_cli_api.py::test_default_app_registers_its_repository_and_can_select_it \
  tests/test_service_cli_api.py::test_webui_repository_switches_task_service_and_isolates_tasks \
  -q -p no:cacheprovider

2 passed
```

`git diff --check` also completed without errors (only existing CRLF warnings).
