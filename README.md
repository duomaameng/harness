# Context-Aware Coding Agent Harness

A deterministic, single-repository coding-agent harness. It retrieves code and
repository conventions before asking a model for one structured action, applies
guardrails before dispatch, records validation feedback, and preserves selected
memory and audit evidence. The core path works offline with `MockLLM`.

## Install

Python 3.11 or newer is required. Create an environment and install the package
with its test tools:

```bash
python -m pip install -e ".[dev]"
```

Initialise the local `.harness/` SQLite and JSONL audit store for a repository:

```bash
harness init --repo .
```

Create and run a task. `--mock-llm` is deterministic and needs neither network
access nor an API key:

```bash
harness run "Update calculator tests" --repo . --mock-llm
```

Use `harness status <run-id> --repo .` to inspect the run after it finishes or
waits for approval.

## Credentials and secrets

For an OpenAI-compatible provider, configure a key through the OS keyring:

```bash
harness auth set
harness auth status --repo .
```

The runtime also checks `HARNESS_API_KEY`, `DEEPSEEK_API_KEY`, and
`OPENAI_API_KEY` in the process environment. A repository `.env` file is only a
local development fallback. It is plaintext, must not be committed, and is
excluded from both Git and Docker build contexts. Prefer the keyring or your
deployment platform's secret store.

## API and WebUI

Start the FastAPI service and WebUI with:

```bash
python -m uvicorn harness.api:app --host 127.0.0.1 --port 8000
```

Or on Windows, run `./scripts/start-webui.ps1`. Create a task through the API,
then open its run page at `http://127.0.0.1:8000/ui/runs/<run-id>`.

## Reports

Each run can be exported as a redacted Markdown or JSON report:

```bash
harness export <run-id> --repo . --format markdown > run-report.md
harness export <run-id> --repo . --format json > run-report.json
```

## Docker

The image contains no keys or other credentials. Build it with:

```bash
docker build -t context-aware-harness:test .
```

Run the API and WebUI against the repository mounted at `/workspace`:

```bash
docker run --rm -p 8000:8000 -v "${PWD}:/workspace" context-aware-harness:test
```

The default command starts the API and WebUI. Inspect the workbench at
[http://localhost:8000](http://localhost:8000) after the container starts.
Because the server starts in `/workspace`, tasks, repository indexing, and
`.harness/` state apply to the mounted repository. The bind mount preserves
that state after the container exits; without it, state is ephemeral.

Run the CLI by overriding that default command:

```bash
docker run --rm -v "${PWD}:/workspace" context-aware-harness:test harness init --repo /workspace
docker run --rm -v "${PWD}:/workspace" context-aware-harness:test harness run "Update tests" --repo /workspace --mock-llm
```

Pass a provider key at runtime through your container platform's secret or
environment-variable mechanism; do not bake it into an image or Dockerfile.

## Deterministic mechanism demo

The end-to-end test copies the small calculator fixture and drives a fixed
`MockLLM` sequence. It proves that context includes memory, a dangerous command
is intercepted, a bad edit receives test feedback, a repair passes validation,
and the run completes:

```bash
python -m pytest tests/test_e2e_demo.py::test_mockllm_demo_context_guardrail_feedback_repair_and_memory -q
```

## Known limits

- This is limited to one repository per task; cross-repository and deployment
  requests stop as out of scope.
- Models can propose only the supported JSON actions; unstructured output is
  feedback, not tool execution.
- Risky writes and commands may require explicit approval; dangerous actions
  are denied.
- The default repair budget is six rounds and repeated identical failures stop
  early.
- The offline mock demonstrates control flow, not autonomous feature quality.
