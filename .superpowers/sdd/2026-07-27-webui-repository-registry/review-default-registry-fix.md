# Review: default WebUI repository registry fix

Commit reviewed: `8d26223b0d347067a1e709286afadb974f796698`

## Findings

### P1 — The regression test does not exercise the real HTTP route

`tests/test_service_cli_api.py:88` obtains the endpoint object with `_endpoint()` and
then calls it directly.  This bypasses FastAPI/ASGI routing, request dispatch, and
response handling, so it is not a test of `POST
/ui/repositories/{repository_id}/select` as served to WebUI clients.  The requested
coverage criterion is real route behaviour, including the successful HTTP `303`
response rather than the former `400 Repository registry is not configured`.

Replace or supplement this test with an ASGI client request to the concrete select
URL (and disable redirect following when asserting the `303`).  Keep the default
`create_app()` construction in that test.  A focused assertion using an explicitly
supplied `RepositoryRegistry` should also verify that `api.state.repository_registry
is registry`, preserving caller-provided registry identity.

## Code assessment

`create_app()` now creates a `RepositoryRegistry` when none is supplied, registers
the default core repository only when absent, exposes that registry on application
state, and passes the same instance to `include_webui()`.  This removes the
unconfigured-registry path for default applications.  An explicit registry remains
the active instance and retains the pre-existing default-repository registration
behaviour.

No files were modified other than this requested review report.  No full test suite
was run.
