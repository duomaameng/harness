# 本地启动 WebUI

本文档说明合并到 `main` 后，如何在 IDE 或终端启动 Harness API/WebUI。

## 1. 打开项目

在 IDE 中打开项目根目录：

```text
C:\Users\duoma\java\harness
```

## 2. 安装依赖

如果当前 Python 环境还没有安装项目依赖，先在 IDE 终端运行：

```powershell
C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pip install -e .[dev]
```

如果你使用自己的 Python 或虚拟环境，也可以运行：

```powershell
python -m pip install -e .[dev]
```

## 3. 启动服务

推荐直接运行脚本：

```powershell
.\scripts\start-webui.ps1
```

默认地址：

```text
http://127.0.0.1:8000
```

也可以指定端口：

```powershell
.\scripts\start-webui.ps1 -Port 8010
```

如果你的 PowerShell 禁止执行脚本，可以临时用：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-webui.ps1
```

## 4. 创建一个可打开的 WebUI run

当前 WebUI 的入口是运行详情页 `/ui/runs/{run_id}`，所以启动服务后需要先创建一个 task 和 run。

在另一个 IDE 终端运行：

```powershell
$task = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/tasks -ContentType 'application/json' -Body '{"title":"IDE test run","description":"Open WebUI from IDE"}'
$run = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/tasks/$($task.id)/runs" -ContentType 'application/json' -Body '{"max_rounds":1}'
"http://127.0.0.1:8000/ui/runs/$($run.id)"
```

复制最后输出的 URL 到浏览器打开。

## 5. IDE 运行配置

如果 IDE 支持 Python run configuration，可以这样配：

- Module name: `uvicorn`
- Parameters: `harness.api:app --host 127.0.0.1 --port 8000 --reload`
- Working directory: `C:\Users\duoma\java\harness`
- Python interpreter: 项目虚拟环境或 Codex runtime Python

## 6. 常见问题

### 端口被占用

换一个端口：

```powershell
.\scripts\start-webui.ps1 -Port 8010
```

创建 run 时也要同步改端口：

```powershell
http://127.0.0.1:8010
```

### 找不到 uvicorn

说明依赖还没装到当前 Python 环境。回到第 2 步安装依赖。

### 只看到 API，没有首页

这是当前实现的预期行为。WebUI 页面是 run detail：

```text
/ui/runs/{run_id}
```

先按第 4 步创建 run，再打开输出的 URL。
