# Local WebUI Startup

This project serves the API and WebUI through FastAPI. The WebUI page is a run detail page:

```text
/ui/runs/{run_id}
```

## 1. Open The Project

Open this folder in your IDE:

```text
C:\Users\duoma\java\harness
```

## 2. Install Dependencies

In the IDE terminal, run:

```powershell
C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pip install -e .[dev]
```

If you use your own Python or virtual environment:

```powershell
python -m pip install -e .[dev]
```

## 3. Start API/WebUI

Run:

```powershell
.\scripts\start-webui.ps1
```

The script prints the actual URL. If port `8000` is already in use, it automatically tries the next free port, for example:

```text
Port 8000 is already in use; using 8001 instead.
URL:     http://127.0.0.1:8001
```

To force a specific port:

```powershell
.\scripts\start-webui.ps1 -Port 8010
```

To fail instead of auto-selecting another port:

```powershell
.\scripts\start-webui.ps1 -NoAutoPort
```

If PowerShell blocks script execution:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-webui.ps1
```

## 4. Create A Demo Run

By default the harness stays offline with `MockLLM` unless credentials are configured.
The built-in real provider default is DeepSeek's OpenAI-compatible Chat Completions API.
For local development, set the API key in your current PowerShell session:

```powershell
$env:DEEPSEEK_API_KEY = "your_deepseek_api_key_here"
$env:HARNESS_LLM_BASE_URL = "https://api.deepseek.com"
$env:HARNESS_LLM_MODEL = "deepseek-v4-pro"
```

If you want Windows to remember it for future terminals, use user-level
environment variables, then open a new terminal:

```powershell
[Environment]::SetEnvironmentVariable("DEEPSEEK_API_KEY", "your_deepseek_api_key_here", "User")
[Environment]::SetEnvironmentVariable("HARNESS_LLM_BASE_URL", "https://api.deepseek.com", "User")
[Environment]::SetEnvironmentVariable("HARNESS_LLM_MODEL", "deepseek-v4-pro", "User")
```

You can also store the key in the OS keyring:

```powershell
harness auth set
```

Repository `.env` files are supported only as a local fallback:

```text
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

For deployment, do not commit a `.env` file with secrets. Configure the same
key as a platform secret or environment variable instead.

Without a configured key, the same run commands below create deterministic offline demo runs.

Keep the server terminal open. In a second terminal, set the base URL to the URL printed by the script:

```powershell
$base = "http://127.0.0.1:8000"
```

If the script selected another port, update `$base`, for example:

```powershell
$base = "http://127.0.0.1:8001"
```

Then create a task and run:

```powershell
$task = Invoke-RestMethod -Method Post -Uri "$base/tasks" -ContentType 'application/json' -Body '{"title":"IDE test run","description":"Open WebUI from IDE"}'
$run = Invoke-RestMethod -Method Post -Uri "$base/tasks/$($task.id)/runs" -ContentType 'application/json' -Body '{"max_rounds":1}'
"$base/ui/runs/$($run.id)"
```

Open the final URL in your browser.

## 5. IDE Run Configuration

If your IDE supports a Python run configuration:

- Module name: `uvicorn`
- Parameters: `harness.api:app --host 127.0.0.1 --port 8000 --reload`
- Working directory: `C:\Users\duoma\java\harness`
- Python interpreter: your project virtualenv or the Codex runtime Python

If the IDE reports port `8000` is already in use, change the parameter to another port:

```text
harness.api:app --host 127.0.0.1 --port 8010 --reload
```

## 6. Troubleshooting

### Port Is Already In Use

The script auto-selects another port by default. Use the URL printed by the script.

To find what is using port `8000`:

```powershell
netstat -ano | findstr :8000
```

To stop a process by PID:

```powershell
taskkill /PID <PID> /F
```

### uvicorn Not Found

Install dependencies again with the same Python used by the script:

```powershell
C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pip install -e .[dev]
```

### There Is No Home Page

That is expected for the current implementation. Create a run first, then open:

```text
/ui/runs/{run_id}
```
