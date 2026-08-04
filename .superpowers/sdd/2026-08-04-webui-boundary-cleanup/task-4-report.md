# Task 4 report: CI TestClient removal remediation

## RED

Command (API-key variables removed for the process):

```powershell
python -m pytest tests/test_service_cli_api.py -q --basetemp .pytest-tmp/ci-testclient-red
```

Result: `14 failed, 27 passed`. The two new JSON ASGI tests failed as intended with:

```text
TypeError: _asgi_post() got an unexpected keyword argument 'json'
```

The other 12 failures are pre-existing WebUI service-isolation failures (for example, `Unknown task run` and missing run content) outside this test-helper-only scope.

## GREEN

```powershell
python -m pytest tests/test_service_cli_api.py -q -k 'webui_repository_management_routes_accept_http_json or webui_switch_uses_injected_service_factory' --basetemp .pytest-tmp/ci-testclient-green
```

Result: `2 passed, 39 deselected`.

## Refactor rerun

Replaced the temporary JSON module lookup with the explicit `json_module` import and reran:

```powershell
python -m pytest tests/test_service_cli_api.py -q -k 'webui_repository_management_routes_accept_http_json or webui_switch_uses_injected_service_factory' --basetemp .pytest-tmp/ci-testclient-refactor
```

Result: `2 passed, 39 deselected`.

## Change

`_asgi_post` now accepts JSON payloads, sends the matching JSON headers/body through the FastAPI ASGI boundary, and captures response body chunks as well as status and headers. No production code or dependency changed.

## Module verification

```powershell
python -m pytest tests/test_service_cli_api.py -q --basetemp .pytest-tmp/ci-testclient-removal
```

Result: `41 passed in 13.11s`.

## Commit

`test: remove TestClient dependency from CI tests` (final SHA reported to the task controller).

## Concern

The earlier red run included 12 WebUI service-isolation failures alongside the intended helper red failures. The final brief-specified module verification is fully green (`41 passed`), so there is no remaining test concern.
