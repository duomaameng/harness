# WebUI Boundary Cleanup Design

## Goal

Correct WebUI repository switching so configured dependencies are preserved, move non-presentation responsibilities out of `harness/webui.py`, add HTTP-level regression coverage, and remove review-identified process artifacts that are not product deliverables.

## Scope

This change addresses review findings 1, 4, and 5, plus the resulting SRP/DIP issue in the WebUI. It does not remove the repository-registry feature or implement the separately missing Docker, CI, README, and end-to-end demo deliverables.

## Architecture

### Service provider

Create `harness/webui_services.py` with `WebUIServiceProvider`. It owns the mapping from registered repository path to `CoreService`.

- It is initialized with the original service and an optional `service_factory: Callable[[Path], CoreService]`.
- It returns the original service for its repository path.
- For another selected repository, it checks its cache before invoking the factory, then caches the created service.
- Its default factory creates `CoreService` with the original service's LLM and validation-command configuration. A caller can provide a factory when it needs fresh per-repository dependencies.

This makes dependency creation explicit and keeps the WebUI from selecting a provider or discarding a caller-supplied MockLLM configuration.

### Route module

Create `harness/webui_routes.py` with `include_webui`. It attaches HTTP routes, validates request payloads, invokes `RepositoryRegistry` and `WebUIServiceProvider`, and delegates HTML generation to rendering functions.

`harness/webui.py` becomes the presentation module: workbench/detail rendering, sidebar and evidence rendering, CSS, and browser JavaScript. It neither creates `CoreService` instances nor coordinates the repository registry.

### Compatibility

The public `include_webui` import remains available from `harness.webui` as a re-export, so existing callers and tests retain their import path. `create_app` continues to call that public interface.

## Behavior and Errors

- No repository selected returns HTTP 400 before task or approval operations.
- An unknown repository selection returns HTTP 404.
- Invalid repository registration or rename input returns HTTP 400.
- Selecting a repository never constructs a service until a route actually needs it.
- A cached service is reused unchanged for later requests.

## Testing

Tests use real FastAPI HTTP requests through `TestClient` for repository JSON endpoints. They verify registering, selecting, renaming, and deleting repositories over HTTP.

Provider-focused tests verify that a second repository receives a service created by the injected factory, that its configured MockLLM/validation settings survive the switch, and that repeated access does not construct duplicate services. Existing direct endpoint tests may remain for focused validation behavior, but they are not the sole coverage of the browser-facing contract.

## Cleanup

Remove committed `.superpowers/sdd/2026-07-27-webui-repository-registry/` process reports and `task-2-report.md`. Revert the uncommitted `TASK_FLOW.md` ignore rule and nonfunctional comments in `harness/service.py`. Product code and product tests are retained.

## Acceptance Criteria

1. `harness/webui.py` has no `CoreService` construction or `RepositoryRegistry` coordination.
2. Switching repositories preserves caller-specified dependency configuration and does not eagerly create or duplicate services.
3. Repository-management routes pass HTTP-level JSON request tests.
4. The identified process artifacts and unrelated uncommitted changes are absent.
5. The focused and full test suites pass in a working Python environment.
