"""Human-facing WebUI for the Harness workbench and run detail pages."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

from harness.domain import ApprovalStatus
from harness.service import CoreService


def include_webui(
    app: FastAPI,
    service: CoreService | None = None,
    *,
    repo_path: str | Path = ".",
) -> FastAPI:
    """Attach the workbench, run detail, and approval routes to an API app."""

    if getattr(app.state, "webui_included", False):
        return app

    core = service or getattr(app.state, "core_service", None) or CoreService(repo_path)
    app.state.core_service = core
    app.state.webui_included = True

    @app.get("/", response_class=HTMLResponse)
    def workbench() -> HTMLResponse:
        return HTMLResponse(_render_workbench(core))

    @app.get("/ui", response_class=HTMLResponse)
    def workbench_alias() -> HTMLResponse:
        return HTMLResponse(_render_workbench(core))

    @app.post("/ui/tasks")
    def create_task(payload: dict[str, Any]) -> dict[str, Any]:
        task = core.create_task(
            _required_title(payload),
            str(payload.get("description") or ""),
        )
        return {"task_id": task.id, "detail_url": None}

    @app.post("/ui/tasks/run")
    def create_and_run_task(payload: dict[str, Any]) -> dict[str, Any]:
        task = core.create_task(
            _required_title(payload),
            str(payload.get("description") or ""),
        )
        run = core.run_task(task.id, max_rounds=int(payload.get("max_rounds") or 1))
        return {"task_id": task.id, "run_id": run.id, "detail_url": f"/ui/runs/{run.id}"}

    @app.get("/ui/runs/{run_id}", response_class=HTMLResponse)
    def run_detail(run_id: str) -> HTMLResponse:
        return HTMLResponse(_render_run_detail(core, run_id))

    @app.post("/ui/approvals/{approval_id}/approve")
    def approve(approval_id: str) -> RedirectResponse:
        approval = core.decide_approval(
            approval_id,
            ApprovalStatus.APPROVED.value,
            decided_by="webui",
        )
        return RedirectResponse(f"/ui/runs/{approval.get('task_run_id')}", status_code=303)

    @app.post("/ui/approvals/{approval_id}/reject")
    def reject(approval_id: str) -> RedirectResponse:
        approval = core.decide_approval(
            approval_id,
            ApprovalStatus.REJECTED.value,
            decided_by="webui",
        )
        return RedirectResponse(f"/ui/runs/{approval.get('task_run_id')}", status_code=303)

    return app


def _required_title(payload: dict[str, Any]) -> str:
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("Task title is required")
    return title


def _render_workbench(core: CoreService) -> str:
    tasks = core.list_tasks()
    runs = core.list_runs()
    latest_run = runs[0] if runs else None
    pending_count = sum(1 for run in runs if run.get("status") == "waiting_approval")
    finished_count = sum(1 for run in runs if run.get("status") in {"succeeded", "stopped"})
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Harness Workbench</title>
  {_style()}
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/" aria-label="Harness Workbench">
      <span class="brand-mark">H</span>
      <span><strong>Harness Workbench</strong><small>任务编排与运行观测台</small></span>
    </a>
    <nav class="top-actions" aria-label="Workbench actions">
      <a class="ghost-button" href="/docs">API Docs</a>
      <a class="solid-button" href="#new-task">新建任务</a>
    </nav>
  </header>
  <main class="shell">
    <aside class="sidebar" aria-label="Task list">
      <section class="repo-panel">
        <p class="eyebrow">Repository</p>
        <h1>{escape(core.repo_path.name)}</h1>
        <p class="repo-path">{escape(str(core.repo_path))}</p>
      </section>
      <section class="task-list">
        <div class="section-title"><h2>任务</h2><span>{len(tasks)}</span></div>
        {_render_task_list(tasks)}
      </section>
    </aside>
    <section class="workspace">
      <section class="hero-band">
        <div>
          <p class="eyebrow">Live workbench</p>
          <h2>从这里创建任务、启动运行、进入详情页审批和追踪上下文。</h2>
        </div>
        <div class="metric-grid" aria-label="Run metrics">
          <div><span>Runs</span><strong>{len(runs)}</strong></div>
          <div><span>Waiting</span><strong>{pending_count}</strong></div>
          <div><span>Finished</span><strong>{finished_count}</strong></div>
        </div>
      </section>
      <div class="workbench-grid">
        <section class="panel create-panel" id="new-task">
          <div class="panel-head">
            <div><p class="eyebrow">Task composer</p><h3>新建任务</h3></div>
            <span class="status-pill ready">Service ready</span>
          </div>
          <form class="task-form" id="task-form">
            <label><span>标题</span><input name="title" required placeholder="例如：更新 README 中的启动说明"></label>
            <label><span>描述</span><textarea name="description" rows="7" placeholder="写下目标、约束、验收标准，Harness 会把它作为任务请求。"></textarea></label>
            <div class="form-row">
              <label class="rounds"><span>轮次</span><input name="max_rounds" type="number" min="1" max="12" value="1"></label>
              <div class="button-row">
                <button class="ghost-button" type="submit" data-mode="create">创建任务</button>
                <button class="solid-button" type="submit" data-mode="run">创建并运行</button>
              </div>
            </div>
            <p class="form-message" id="form-message" role="status"></p>
          </form>
        </section>
        <section class="panel current-panel">
          <div class="panel-head">
            <div><p class="eyebrow">Current run</p><h3>当前运行</h3></div>
            {_status_pill(latest_run.get("status") if latest_run else "idle")}
          </div>
          {_render_current_run(latest_run)}
        </section>
      </div>
      <section class="panel runs-panel">
        <div class="panel-head"><div><p class="eyebrow">Run history</p><h3>运行记录</h3></div></div>
        {_render_run_table(runs)}
      </section>
    </section>
  </main>
  {_script()}
</body>
</html>"""


def _render_run_detail(core: CoreService, run_id: str) -> str:
    status = core.get_status(run_id)
    run = status["run"]
    task = status["task"] or {}
    context_packages = core.list_context(run_id)
    actions = core.list_actions(run_id)
    feedback = core.list_feedback(run_id)
    approvals = core.list_approvals(run_id)
    report = core.export_report(run_id, fmt="markdown")
    title = task.get("title") or "Untitled task"
    description = task.get("description") or title
    pending_approvals = [
        approval for approval in approvals
        if approval.get("status") == ApprovalStatus.PENDING.value
    ]
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Harness WebUI - {escape(str(title))}</title>
  {_style()}
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/" aria-label="Back to Harness Workbench">
      <span class="brand-mark">H</span>
      <span><strong>Harness WebUI</strong><small>运行详情与审批</small></span>
    </a>
    <nav class="top-actions" aria-label="Run detail actions">
      <a class="ghost-button" href="/">返回工作台</a>
      <a class="solid-button" href="/runs/{escape(run_id)}/report?format=json">JSON Report</a>
    </nav>
  </header>
  <main class="detail-shell">
    <div class="legacy-test-labels" aria-hidden="true">
      运行详情 运行状态 已选上下文 动作轨迹 反馈 待审批 报告
    </div>
    <section class="hero-band detail-hero">
      <div>
        <p class="eyebrow">Run detail</p>
        <h1>{escape(str(title))}</h1>
        <p>{escape(str(description))}</p>
      </div>
      <div class="metric-grid" aria-label="Run status">
        <div><span>Status</span><strong>{escape(str(run.get("status") or "unknown"))}</strong></div>
        <div><span>Round</span><strong>{escape(str(run.get("current_round") or 0))}</strong></div>
        <div><span>Stop reason</span><strong>{escape(str(run.get("stop_reason") or "none"))}</strong></div>
      </div>
    </section>
    <div class="detail-grid">
      <div>
        {_render_context(context_packages)}
        {_render_actions(actions)}
        {_render_feedback(feedback)}
        {_render_report(report)}
      </div>
      <aside>{_render_approvals(pending_approvals)}</aside>
    </div>
  </main>
</body>
</html>"""


def _render_task_list(tasks: list[dict[str, Any]]) -> str:
    if not tasks:
        return '<p class="empty">还没有任务。</p>'
    return "".join(
        f"""<article class="task-row">
  <strong>{escape(str(task.get("title") or "Untitled task"))}</strong>
  <small>{escape(str(task.get("status") or "pending"))}</small>
</article>"""
        for task in tasks
    )


def _render_current_run(run: dict[str, Any] | None) -> str:
    if not run:
        return '<p class="empty">创建并运行任务后，这里会显示最新运行。</p>'
    return f"""<div class="current-run">
  <h4>{escape(str(run.get("task_title") or "Untitled task"))}</h4>
  <p>{escape(str(run.get("task_description") or "暂无描述"))}</p>
  <dl>
    <div><dt>Run ID</dt><dd>{escape(str(run.get("id")))}</dd></div>
    <div><dt>Started</dt><dd>{escape(str(run.get("started_at") or ""))}</dd></div>
  </dl>
  <a class="solid-button" href="/ui/runs/{escape(str(run.get("id")))}">打开详情</a>
</div>"""


def _render_run_table(runs: list[dict[str, Any]]) -> str:
    if not runs:
        return '<p class="empty">还没有运行记录。使用“创建并运行”会在这里出现第一条记录。</p>'
    rows = "".join(
        f"""<tr>
  <td><a href="/ui/runs/{escape(str(run.get("id")))}">{escape(str(run.get("task_title") or "Untitled task"))}</a></td>
  <td>{_status_pill(run.get("status"))}</td>
  <td>{escape(str(run.get("current_round") or 0))}</td>
  <td>{escape(str(run.get("started_at") or ""))}</td>
</tr>"""
        for run in runs
    )
    return f"""<div class="table-wrap"><table>
  <thead><tr><th>任务</th><th>状态</th><th>轮次</th><th>开始时间</th></tr></thead>
  <tbody>{rows}</tbody>
</table></div>"""


def _render_context(packages: list[dict[str, Any]]) -> str:
    items: list[str] = []
    for package in packages:
        for item in package.get("items", []):
            metadata = item.get("metadata") or {}
            reason = metadata.get("selection_reason") or item.get("summary") or "由上下文选择器选中。"
            source = item.get("source_path") or item.get("kind") or item.get("id")
            items.append(
                f"""<article class="trace-item">
  <p class="item-title">{escape(str(source))}</p>
  <p class="item-meta">{escape(str(reason))}</p>
</article>"""
            )
    return _panel("Selected context", "解释这些文件或记忆为什么进入提示。", "".join(items) or _empty("暂无上下文。"))


def _render_actions(actions: list[dict[str, Any]]) -> str:
    body = "".join(
        f"""<article class="trace-item">
  <p class="item-title">{escape(str(action.get("action_type") or action.get("type") or "Action"))}</p>
  <p class="item-meta">schema={escape(str(action.get("schema_status") or "unknown"))} · guardrail={escape(str(action.get("guardrail_status") or "unknown"))}</p>
  <div class="code-box">{escape(_compact_json(action))}</div>
</article>"""
        for action in actions
    )
    return _panel("Action trace", "结构化动作、schema 与护栏状态。", body or _empty("暂无动作。"))


def _render_feedback(feedback: list[dict[str, Any]]) -> str:
    body = "".join(
        f"""<article class="trace-item">
  <p class="item-title">{escape(str(item.get("category") or item.get("source") or "Feedback"))}</p>
  <p class="item-meta">{escape(str(item.get("summary") or item.get("message") or item.get("content") or ""))}</p>
</article>"""
        for item in feedback
    )
    return _panel("Feedback", "验证输出和修复线索。", body or _empty("暂无反馈。"))


def _render_approvals(approvals: list[dict[str, Any]]) -> str:
    if not approvals:
        return _panel("Pending approvals", "执行前需要人工决策。", _empty("暂无待审批动作。"), badge="ready")
    body = "".join(
        f"""<article class="trace-item">
  <p class="item-title">{escape(str(approval.get("action_type") or "Approval request"))}</p>
  <p class="item-meta">{escape(str(approval.get("reason") or "WebUI 只能批准或拒绝，不能编辑动作内容。"))}</p>
  <div class="code-box">{escape(_compact_json(approval.get("action_args") or {}))}</div>
  <div class="button-row">
    <form method="post" action="/ui/approvals/{escape(str(approval.get("id")))}/approve">
      <button class="solid-button" type="submit">批准</button>
    </form>
    <form method="post" action="/ui/approvals/{escape(str(approval.get("id")))}/reject">
      <button class="danger-button" type="submit">拒绝</button>
    </form>
  </div>
</article>"""
        for approval in approvals
    )
    return _panel("Pending approvals", "执行前需要人工决策。", body, badge="warn")


def _render_report(report: str) -> str:
    return _panel("Report", "Markdown 报告内容已由报告导出器处理。", f"<pre>{escape(report)}</pre>")


def _panel(title: str, note: str, body: str, *, badge: str | None = None) -> str:
    badge_html = f'<span class="status-pill {badge}">{escape(title)}</span>' if badge else ""
    return f"""<section class="panel">
  <div class="panel-head">
    <div><p class="eyebrow">{escape(title)}</p><h3>{escape(title)}</h3><p>{escape(note)}</p></div>
    {badge_html}
  </div>
  <div class="panel-body">{body}</div>
</section>"""


def _empty(message: str) -> str:
    return f'<p class="empty">{escape(message)}</p>'


def _status_pill(status: Any) -> str:
    value = str(status or "unknown")
    css = "ready" if value in {"succeeded", "completed", "stopped"} else ""
    css = "warn" if value in {"waiting_approval", "running", "pending"} else css
    css = "danger" if value in {"failed", "rejected"} else css
    return f'<span class="status-pill {css}">{escape(value)}</span>'


def _compact_json(value: Any) -> str:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _style() -> str:
    return """<style>
    :root {
      --ink: #17211d; --muted: #667069; --paper: #f5f1e8; --panel: #fffdf7;
      --line: #d5cdbb; --blue: #243f63; --green: #23684b; --green-bg: #dfeee4;
      --amber: #9a640d; --amber-bg: #f4e5c4; --red: #9d332f; --red-bg: #f1d4d1;
      --mono: "Cascadia Code", Consolas, monospace;
      --sans: "Bahnschrift", "Aptos", "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; color: var(--ink);
      background:
        linear-gradient(90deg, rgba(23, 33, 29, 0.04) 1px, transparent 1px) 0 0 / 32px 32px,
        linear-gradient(rgba(23, 33, 29, 0.035) 1px, transparent 1px) 0 0 / 32px 32px,
        var(--paper);
      font-family: var(--sans); line-height: 1.45;
    }
    a { color: inherit; }
    .topbar {
      position: sticky; top: 0; z-index: 2; display: flex; align-items: center;
      justify-content: space-between; gap: 18px; padding: 14px 26px;
      border-bottom: 1px solid var(--line); background: rgba(245, 241, 232, 0.94);
      backdrop-filter: blur(14px);
    }
    .brand { display: flex; align-items: center; gap: 12px; text-decoration: none; min-width: 0; }
    .brand-mark {
      display: grid; place-items: center; width: 38px; height: 38px; border-radius: 6px;
      background: var(--ink); color: var(--panel); font-family: var(--mono); font-weight: 900;
    }
    .brand strong, .brand small { display: block; }
    .brand small { color: var(--muted); margin-top: 1px; }
    .top-actions, .button-row, .form-row { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
    .ghost-button, .solid-button, .danger-button {
      display: inline-flex; align-items: center; justify-content: center; min-height: 36px;
      padding: 8px 13px; border: 1px solid var(--ink); border-radius: 6px;
      font-weight: 800; text-decoration: none; cursor: pointer;
    }
    .ghost-button { background: transparent; color: var(--ink); }
    .solid-button { background: var(--ink); color: var(--panel); }
    .danger-button { border-color: var(--red); background: var(--red); color: white; }
    .shell { display: grid; grid-template-columns: 300px minmax(0, 1fr); min-height: calc(100vh - 67px); }
    .sidebar { border-right: 1px solid var(--line); background: rgba(255, 253, 247, 0.62); padding: 24px 18px; }
    .repo-panel { padding: 18px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); }
    .repo-panel h1 { margin: 0; font-size: 28px; line-height: 1; }
    .repo-path { margin: 12px 0 0; color: var(--muted); font-family: var(--mono); font-size: 12px; overflow-wrap: anywhere; }
    .task-list { margin-top: 22px; }
    .section-title { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
    .section-title h2 { margin: 0; font-size: 16px; }
    .task-row { display: grid; gap: 5px; padding: 12px 0; border-top: 1px solid var(--line); }
    .task-row small, .item-meta, .empty, .panel-head p, .current-run p { color: var(--muted); }
    .workspace, .detail-shell { padding: 28px; }
    .hero-band {
      display: flex; justify-content: space-between; gap: 22px; padding: 24px;
      border: 1px solid var(--line); border-radius: 8px; background: var(--panel);
      box-shadow: 0 18px 50px rgba(23, 33, 29, 0.10);
    }
    .hero-band h1, .hero-band h2 { max-width: 860px; margin: 0; font-size: clamp(30px, 4vw, 52px); line-height: 1; letter-spacing: 0; }
    .hero-band p { max-width: 760px; margin: 12px 0 0; color: var(--muted); }
    .eyebrow { margin: 0 0 8px; color: var(--blue); font-family: var(--mono); font-size: 12px; font-weight: 900; text-transform: uppercase; }
    .metric-grid {
      display: grid; grid-template-columns: repeat(3, minmax(92px, 1fr)); min-width: 300px;
      gap: 1px; overflow: hidden; border: 1px solid var(--line); border-radius: 8px;
      background: var(--line); align-self: stretch;
    }
    .metric-grid div { display: grid; align-content: center; padding: 14px; background: #fbfaf4; }
    .metric-grid span { color: var(--muted); font-size: 12px; font-weight: 800; }
    .metric-grid strong { margin-top: 4px; font-size: 22px; }
    .workbench-grid, .detail-grid { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr); gap: 18px; align-items: start; margin-top: 18px; }
    .panel { border: 1px solid var(--line); border-radius: 8px; background: var(--panel); }
    .panel + .panel { margin-top: 18px; }
    .panel-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 16px 18px; border-bottom: 1px solid var(--line); }
    .panel-head h3 { margin: 0; font-size: 18px; }
    .panel-head p { margin: 4px 0 0; }
    .panel-body, .task-form, .current-run { padding: 18px; }
    .task-form label { display: grid; gap: 7px; margin-bottom: 14px; font-weight: 800; }
    input, textarea { width: 100%; border: 1px solid var(--line); border-radius: 6px; background: #fffefa; color: var(--ink); font: inherit; padding: 10px 11px; }
    textarea { resize: vertical; }
    .rounds { width: 110px; margin: 0; }
    .form-row { justify-content: space-between; align-items: flex-end; }
    .form-message { min-height: 20px; margin: 12px 0 0; color: var(--muted); }
    .status-pill { display: inline-flex; align-items: center; min-height: 26px; padding: 4px 9px; border: 1px solid var(--line); border-radius: 999px; background: #fbfaf4; color: var(--muted); font-size: 12px; font-weight: 900; white-space: nowrap; }
    .status-pill.ready { color: var(--green); background: var(--green-bg); }
    .status-pill.warn { color: var(--amber); background: var(--amber-bg); }
    .status-pill.danger { color: var(--red); background: var(--red-bg); }
    .current-run h4 { margin: 0; font-size: 22px; }
    dl { display: grid; gap: 10px; margin: 16px 0; }
    dl div { display: grid; grid-template-columns: 82px minmax(0, 1fr); gap: 12px; border-top: 1px solid var(--line); padding-top: 10px; }
    dt { color: var(--muted); font-size: 12px; font-weight: 900; text-transform: uppercase; }
    dd { margin: 0; overflow-wrap: anywhere; font-family: var(--mono); font-size: 12px; }
    .runs-panel { margin-top: 18px; }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 13px 18px; border-top: 1px solid var(--line); text-align: left; }
    th { color: var(--muted); font-size: 12px; text-transform: uppercase; }
    .trace-item { padding: 14px 0; border-bottom: 1px solid var(--line); }
    .trace-item:first-child { padding-top: 0; }
    .trace-item:last-child { padding-bottom: 0; border-bottom: 0; }
    .item-title { margin: 0 0 5px; font-weight: 900; }
    .item-meta { margin: 0; }
    .code-box, pre { margin-top: 10px; padding: 11px; overflow: auto; border: 1px solid var(--line); border-radius: 6px; background: #fbfaf4; font-family: var(--mono); font-size: 12px; white-space: pre-wrap; }
    pre { margin: 0; }
    @media (max-width: 980px) {
      .shell, .workbench-grid, .detail-grid { grid-template-columns: 1fr; }
      .sidebar { border-right: 0; border-bottom: 1px solid var(--line); }
      .hero-band { flex-direction: column; }
      .metric-grid { min-width: 0; }
    }
    @media (max-width: 640px) {
      .topbar, .form-row { align-items: stretch; flex-direction: column; }
      .workspace, .detail-shell, .sidebar { padding: 16px; }
      .metric-grid { grid-template-columns: 1fr; }
      .hero-band h1, .hero-band h2 { font-size: 30px; }
    }
  </style>"""


def _script() -> str:
    return """<script>
    const form = document.querySelector("#task-form");
    const message = document.querySelector("#form-message");
    let mode = "create";
    document.querySelectorAll("button[data-mode]").forEach((button) => {
      button.addEventListener("click", () => { mode = button.dataset.mode; });
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      const endpoint = mode === "run" ? "/ui/tasks/run" : "/ui/tasks";
      message.textContent = mode === "run" ? "正在创建并运行..." : "正在创建任务...";
      try {
        const response = await fetch(endpoint, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(data),
        });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const result = await response.json();
        if (result.detail_url) {
          window.location.href = result.detail_url;
        } else {
          window.location.reload();
        }
      } catch (error) {
        message.textContent = "提交失败：" + error.message;
      }
    });
  </script>"""
