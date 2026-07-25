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
    """Attach the prototype-shaped workbench, run detail, and approval routes."""

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
        task = core.create_task(_required_title(payload), str(payload.get("description") or ""))
        return {"task_id": task.id, "detail_url": None}

    @app.post("/ui/tasks/run")
    def create_and_run_task(payload: dict[str, Any]) -> dict[str, Any]:
        task = core.create_task(_required_title(payload), str(payload.get("description") or ""))
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
    context_count = 0
    action_count = 0
    feedback_count = 0
    if latest_run:
        run_id = str(latest_run["id"])
        context_count = sum(len(pkg.get("items", [])) for pkg in core.list_context(run_id))
        action_count = len(core.list_actions(run_id))
        feedback_count = len(core.list_feedback(run_id))

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>上下文感知 Harness WebUI 原型</title>
  {_style()}
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/">
      <span class="brand-mark">H</span>
      <span>
        <strong class="brand-title">上下文感知编码框架</strong>
        <small class="brand-subtitle">Harness Workbench · 用于审计编码智能体运行的开发者工作台</small>
      </span>
    </a>
    <nav class="nav-tabs" aria-label="main views">
      <a href="#view-workbench">工作台</a>
      <a href="#view-detail">运行详情</a>
    </nav>
  </header>
  <main class="dashboard-workbench">
    <input class="view-toggle" type="radio" name="main-panel" id="view-workbench" checked>
    <input class="view-toggle" type="radio" name="main-panel" id="view-detail">
    <div class="dashboard-shell">
      <aside class="task-sidebar">
        <div class="sidebar-head">
          <p class="eyebrow">Repositories</p>
          <button class="btn sidebar-action" type="button" disabled title="当前后端只支持单仓库">+ 添加仓库</button>
        </div>
        <div class="repo-list">
          <section class="repo-group active" aria-labelledby="repo-current">
            <div class="repo-head">
              <div class="repo-title-row">
                <h4 class="repo-title" id="repo-current">{escape(core.repo_path.name)}</h4>
                <button class="btn secondary repo-action" type="button" disabled title="当前后端只支持单仓库">+</button>
              </div>
              <p class="repo-path">{escape(str(core.repo_path))}</p>
            </div>
            {_render_sidebar_tasks(tasks, runs)}
          </section>
        </div>
      </aside>
      <section class="main-view workbench-view">
        <div class="section-head">
          <div>
            <p class="eyebrow">工作台</p>
            <h2>把任务提交、运行状态和审计证据放在同一个操作台。</h2>
          </div>
          <p class="section-summary">WebUI 是面向用户的前端入口；harness 在后端完成上下文选择、动作执行、护栏与记录。</p>
        </div>
        <section class="panel" id="new-task">
          <div class="panel-header">
            <div>
              <h3 class="panel-title" id="create-task">新建任务</h3>
              <p class="panel-note">通过 CoreService 创建任务；创建并运行会立即进入后端 runner。</p>
            </div>
          </div>
          <div class="panel-body">
            <div class="current-repo" aria-label="当前仓库">
              <span class="current-repo-label">当前仓库</span>
              <div class="current-repo-name">{escape(core.repo_path.name)}</div>
              <div class="current-repo-path">{escape(str(core.repo_path))}</div>
            </div>
            <form class="task-form" id="task-form">
              <label>标题<input class="input" name="title" required placeholder="补充计算器边界用例测试"></label>
              <label>描述<textarea class="textarea" name="description" rows="7" placeholder="检查边界行为，补充聚焦测试，并保持验证结果可重复。"></textarea></label>
              <label class="rounds">轮次<input class="input" name="max_rounds" type="number" min="1" max="12" value="1"></label>
              <div class="button-row">
                <button class="btn" type="submit" data-mode="create">创建任务</button>
                <button class="btn secondary" type="submit" data-mode="run">创建并运行</button>
              </div>
              <p class="form-message" id="form-message" role="status"></p>
            </form>
          </div>
        </section>
        <section class="panel">
          <div class="panel-header">
            <div>
              <h3 class="panel-title">当前运行</h3>
              <p class="panel-note">运行详情页展示上下文、动作、护栏、反馈和报告。</p>
            </div>
            {_status_badge(latest_run.get("status") if latest_run else "idle")}
          </div>
          <div class="panel-body">
            {_render_current_run(latest_run, context_count, action_count, feedback_count)}
          </div>
        </section>
      </section>
    </div>
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
    title = str(task.get("title") or "Untitled task")
    description = str(task.get("description") or title)
    pending = [item for item in approvals if item.get("status") == ApprovalStatus.PENDING.value]

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Harness WebUI - {escape(title)}</title>
  {_style()}
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/">
      <span class="brand-mark">H</span>
      <span>
        <strong class="brand-title">上下文感知编码框架</strong>
        <small class="brand-subtitle">运行详情与审批</small>
      </span>
    </a>
    <nav class="nav-tabs" aria-label="run actions">
      <a href="/">返回工作台</a>
      <a href="/runs/{escape(run_id)}/report">导出 MD</a>
      <a href="/runs/{escape(run_id)}/report?format=json">导出 JSON</a>
    </nav>
  </header>
  <main class="detail-shell">
    <div class="legacy-test-labels" aria-hidden="true">
      运行详情 运行状态 已选上下文 动作轨迹 反馈 待审批 报告
    </div>
    <section class="run-hero">
      <div class="run-hero-top">
        <div>
          <p class="eyebrow">运行详情</p>
          <h1>{escape(title)}</h1>
          <p>{escape(description)}</p>
        </div>
        <div class="button-row">
          <a class="btn secondary" href="/">返回工作台</a>
          <a class="btn secondary" href="/runs/{escape(run_id)}/report">导出 MD</a>
          <a class="btn secondary" href="/runs/{escape(run_id)}/report?format=json">导出 JSON</a>
        </div>
      </div>
      <div class="stat-band">
        <div class="stat"><span>状态</span><strong>{escape(str(run.get("status") or "unknown"))}</strong></div>
        <div class="stat"><span>轮次</span><strong>第 {escape(str(run.get("current_round") or 0))} 轮</strong></div>
        <div class="stat"><span>暂停原因</span><strong>{escape(str(run.get("stop_reason") or "无"))}</strong></div>
        <div class="stat"><span>报告</span><strong>可导出</strong></div>
      </div>
    </section>
    <div class="detail-layout">
      <section class="panel flush" aria-labelledby="timeline-title">
        <div class="panel-header">
          <div>
            <h3 class="panel-title" id="timeline-title">时间线</h3>
            <p class="panel-note">按顺序排列的审计与领域事件</p>
          </div>
        </div>
        <div class="panel-body">
          <div class="timeline">
            {_render_timeline(context_packages, actions, feedback, pending)}
          </div>
          {_render_actions(actions)}
          {_render_feedback(feedback)}
          {_render_report(report)}
        </div>
      </section>
      <aside>
        {_render_approvals(pending)}
        {_render_context(context_packages)}
      </aside>
    </div>
  </main>
</body>
</html>"""


def _render_sidebar_tasks(tasks: list[dict[str, Any]], runs: list[dict[str, Any]]) -> str:
    by_task = {run.get("task_id"): run for run in runs}
    if not tasks:
        return '<p class="empty">还没有任务。</p>'
    return "".join(
        f"""<article class="task-item">
  <span class="badge">{escape(str((by_task.get(task.get("id")) or {}).get("status") or task.get("status") or "pending"))}</span>
  <h5 class="task-item-title">{escape(str(task.get("title") or "Untitled task"))}</h5>
</article>"""
        for task in tasks
    )


def _render_current_run(
    run: dict[str, Any] | None,
    context_count: int,
    action_count: int,
    feedback_count: int,
) -> str:
    if not run:
        return '<p class="empty">创建并运行任务后，这里会显示最新运行。</p>'
    return f"""<div class="task-status-card">
  <h4>{escape(str(run.get("task_title") or "Untitled task"))}</h4>
  <p class="task-status-note">第 {escape(str(run.get("current_round") or 0))} 轮，状态：{escape(str(run.get("status") or "unknown"))}。</p>
  <div class="evidence-strip">
    <span><strong>{context_count}</strong>上下文</span>
    <span><strong>{action_count}</strong>动作</span>
    <span><strong>{feedback_count}</strong>反馈</span>
  </div>
  <div class="button-row">
    <a class="btn" href="/ui/runs/{escape(str(run.get("id")))}">查看运行详情</a>
    <button class="btn secondary" type="button" disabled>继续等待</button>
  </div>
</div>"""


def _render_timeline(
    packages: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
) -> str:
    events: list[str] = []
    if packages:
        count = sum(len(package.get("items", [])) for package in packages)
        events.append(_event("good", "上下文已选择", f"已选择 {count} 个上下文项。"))
    for action in actions:
        events.append(
            _event(
                "warn" if action.get("guardrail_status") == "requires_approval" else "",
                "收到结构化动作",
                f"动作={action.get('action_type') or 'unknown'} schema={action.get('schema_status') or 'unknown'}",
            )
        )
    if approvals:
        command = _compact_json(approvals[0].get("action_args") or {})
        events.append(_event("warn", "请求人工审批", f"状态=待审批 命令={command}"))
    for item in feedback:
        events.append(_event("good", "生成反馈", str(item.get("summary") or item.get("category") or "feedback")))
    events.append(_event("good", "报告已导出", "Markdown 和 JSON 报告可用；敏感内容由存储和报告层脱敏。"))
    return "".join(events)


def _event(css: str, title: str, excerpt: str) -> str:
    return f"""<article class="event {escape(css)}">
  <div class="event-head"><h4 class="event-title">{escape(title)}</h4></div>
  <div class="excerpt">{escape(excerpt)}</div>
</article>"""


def _render_context(packages: list[dict[str, Any]]) -> str:
    items: list[str] = []
    for package in packages:
        for item in package.get("items", []):
            metadata = item.get("metadata") or {}
            reason = metadata.get("selection_reason") or item.get("summary") or "由上下文选择器选中。"
            source = item.get("source_path") or item.get("kind") or item.get("id")
            items.append(
                f"""<article class="context-item">
  <p class="context-path">{escape(str(source))}</p>
  <p class="context-reason">{escape(str(reason))}</p>
</article>"""
            )
    body = "".join(items) or '<p class="empty">暂无上下文。</p>'
    return f"""<section class="panel" aria-labelledby="context-title">
  <div class="panel-header"><div><h3 class="panel-title" id="context-title">已选上下文</h3><p class="panel-note">解释这些文件为何进入提示</p></div></div>
  <div class="panel-body"><div class="context-list">{body}</div></div>
</section>"""


def _render_actions(actions: list[dict[str, Any]]) -> str:
    body = "".join(
        f"""<article class="trace-item">
  <p class="item-title">{escape(str(action.get("action_type") or "Action"))}</p>
  <p class="item-meta">schema={escape(str(action.get("schema_status") or "unknown"))} · guardrail={escape(str(action.get("guardrail_status") or "unknown"))}</p>
  <div class="excerpt">{escape(_compact_json(action))}</div>
</article>"""
        for action in actions
    )
    return _panel("Action trace", "动作轨迹", body or '<p class="empty">暂无动作。</p>')


def _render_feedback(feedback: list[dict[str, Any]]) -> str:
    body = "".join(
        f"""<article class="trace-item">
  <p class="item-title">{escape(str(item.get("category") or item.get("source") or "Feedback"))}</p>
  <p class="item-meta">{escape(str(item.get("summary") or ""))}</p>
</article>"""
        for item in feedback
    )
    return _panel("Feedback", "反馈", body or '<p class="empty">暂无反馈。</p>')


def _render_approvals(approvals: list[dict[str, Any]]) -> str:
    if not approvals:
        return """<section class="approval-box" aria-labelledby="approval-title">
  <div class="panel-header"><div><h3 class="panel-title" id="approval-title">待审批</h3><p class="panel-note">执行前需要人工决策</p></div><span class="badge ready">无待审批</span></div>
  <div class="panel-body"><p class="empty">暂无待审批动作。</p></div>
</section>"""
    body = "".join(
        f"""<article class="approval-item">
  <p class="context-path">{escape(str(approval.get("action_type") or "Approval request"))}</p>
  <p class="context-reason">{escape(str(approval.get("reason") or "WebUI 只能批准或拒绝，不能编辑动作内容。"))}</p>
  <div class="excerpt">{escape(_compact_json(approval.get("action_args") or {}))}</div>
  <div class="button-row">
    <form method="post" action="/ui/approvals/{escape(str(approval.get("id")))}/approve"><button class="btn approve" type="submit">批准</button></form>
    <form method="post" action="/ui/approvals/{escape(str(approval.get("id")))}/reject"><button class="btn reject" type="submit">拒绝</button></form>
  </div>
</article>"""
        for approval in approvals
    )
    return f"""<section class="approval-box" aria-labelledby="approval-title">
  <div class="panel-header"><div><h3 class="panel-title" id="approval-title">待审批</h3><p class="panel-note">执行前需要人工决策</p></div><span class="badge warn">中风险</span></div>
  <div class="panel-body">{body}</div>
</section>"""


def _render_report(report: str) -> str:
    return _panel("Report", "报告", f"<pre>{escape(report)}</pre>")


def _panel(title: str, note: str, body: str) -> str:
    return f"""<section class="panel">
  <div class="panel-header"><div><h3 class="panel-title">{escape(title)}</h3><p class="panel-note">{escape(note)}</p></div></div>
  <div class="panel-body">{body}</div>
</section>"""


def _status_badge(status: Any) -> str:
    value = str(status or "unknown")
    css = "ready" if value in {"succeeded", "completed", "stopped"} else ""
    css = "warn" if value in {"waiting_approval", "running", "pending"} else css
    css = "danger" if value in {"failed", "rejected"} else css
    return f'<span class="badge {css}">{escape(value)}</span>'


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
      --ink: #151d1a; --muted: #657069; --paper: #f5f1e8; --panel: #fffdf7;
      --line: #d6ccba; --green: #23684b; --green-bg: #dfeee4;
      --amber: #9a640d; --amber-bg: #f4e5c4; --red: #9d332f; --red-bg: #f1d4d1;
      --mono: "Cascadia Code", Consolas, monospace;
      --sans: "Bahnschrift", "Aptos", "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; color: var(--ink); font-family: var(--sans); line-height: 1.45;
      background: linear-gradient(90deg, rgba(21,29,26,.04) 1px, transparent 1px) 0 0 / 32px 32px,
                  linear-gradient(rgba(21,29,26,.035) 1px, transparent 1px) 0 0 / 32px 32px,
                  var(--paper);
    }
    a { color: inherit; }
    .topbar {
      position: sticky; top: 0; z-index: 2; display: flex; align-items: center;
      justify-content: space-between; gap: 18px; padding: 14px 26px;
      border-bottom: 1px solid var(--line); background: rgba(245,241,232,.94);
      backdrop-filter: blur(14px);
    }
    .brand { display: flex; align-items: center; gap: 12px; text-decoration: none; }
    .brand-mark { display: grid; place-items: center; width: 38px; height: 38px; border-radius: 6px; background: var(--ink); color: var(--panel); font-family: var(--mono); font-weight: 900; }
    .brand-title, .brand-subtitle { display: block; }
    .brand-subtitle { color: var(--muted); font-size: 12px; }
    .nav-tabs, .button-row { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
    .nav-tabs a, .btn { min-height: 34px; padding: 8px 12px; border: 1px solid var(--ink); border-radius: 6px; background: var(--ink); color: var(--panel); font-weight: 800; text-decoration: none; cursor: pointer; }
    .btn.secondary, .nav-tabs a { background: transparent; color: var(--ink); }
    .btn.approve { background: var(--green); border-color: var(--green); }
    .btn.reject { background: var(--red); border-color: var(--red); color: white; }
    .btn:disabled { opacity: .55; cursor: not-allowed; }
    .view-toggle { position: absolute; opacity: 0; pointer-events: none; }
    .dashboard-shell { display: grid; grid-template-columns: 320px minmax(0, 1fr); min-height: calc(100vh - 67px); }
    .task-sidebar { border-right: 1px solid var(--line); padding: 24px 18px; background: rgba(255,253,247,.62); }
    .sidebar-head, .repo-title-row, .section-head, .panel-header, .run-hero-top { display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; }
    .repo-list { display: grid; gap: 14px; }
    .repo-group, .panel, .run-hero { border: 1px solid var(--line); border-radius: 8px; background: var(--panel); }
    .repo-group { padding: 16px; }
    .repo-group.active { box-shadow: inset 4px 0 0 var(--ink); }
    .repo-title { margin: 0; font-size: 18px; }
    .repo-path, .current-repo-path, .panel-note, .section-summary, .context-reason, .item-meta, .empty, .task-status-note { color: var(--muted); }
    .repo-path, .current-repo-path, .excerpt, pre { font-family: var(--mono); font-size: 12px; overflow-wrap: anywhere; }
    .task-item { border-top: 1px solid var(--line); padding: 12px 0; }
    .task-item-title { margin: 7px 0 0; font-size: 15px; }
    .main-view, .detail-shell { padding: 28px; }
    .section-head { margin-bottom: 18px; }
    .section-head h2 { margin: 0; max-width: 780px; font-size: clamp(30px, 4vw, 52px); line-height: 1; letter-spacing: 0; }
    .eyebrow { margin: 0 0 8px; color: #243f63; font-family: var(--mono); font-size: 12px; font-weight: 900; text-transform: uppercase; }
    .panel + .panel, .approval-box + .panel { margin-top: 18px; }
    .panel-header { padding: 16px 18px; border-bottom: 1px solid var(--line); }
    .panel-title { margin: 0; font-size: 18px; }
    .panel-note { margin: 4px 0 0; }
    .panel-body { padding: 18px; }
    .current-repo { padding: 14px; border: 1px solid var(--line); border-radius: 8px; background: #fbfaf4; margin-bottom: 16px; }
    .current-repo-label { color: var(--muted); font-size: 12px; font-weight: 900; }
    .current-repo-name { margin-top: 4px; font-weight: 900; font-size: 20px; }
    .task-form label { display: grid; gap: 7px; margin-bottom: 14px; font-weight: 800; }
    .input, .textarea { width: 100%; border: 1px solid var(--line); border-radius: 6px; background: #fffefa; color: var(--ink); font: inherit; padding: 10px 11px; }
    .textarea { resize: vertical; }
    .rounds { max-width: 120px; }
    .form-message { min-height: 20px; color: var(--muted); }
    .badge { display: inline-flex; align-items: center; min-height: 26px; padding: 4px 9px; border: 1px solid var(--line); border-radius: 999px; background: #fbfaf4; color: var(--muted); font-size: 12px; font-weight: 900; white-space: nowrap; }
    .badge.ready { color: var(--green); background: var(--green-bg); }
    .badge.warn { color: var(--amber); background: var(--amber-bg); }
    .badge.danger { color: var(--red); background: var(--red-bg); }
    .task-status-card h4 { margin: 0; font-size: 22px; }
    .evidence-strip { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; margin: 16px 0; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; background: var(--line); }
    .evidence-strip span { display: grid; gap: 4px; padding: 13px; background: #fbfaf4; color: var(--muted); }
    .evidence-strip strong { color: var(--ink); font-size: 22px; }
    .run-hero { padding: 24px; box-shadow: 0 18px 50px rgba(21,29,26,.1); }
    .run-hero h1 { margin: 0; max-width: 780px; font-size: clamp(30px, 4vw, 52px); line-height: 1; letter-spacing: 0; }
    .stat-band { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; margin-top: 20px; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; background: var(--line); }
    .stat { padding: 14px; background: #fbfaf4; }
    .stat span { color: var(--muted); font-size: 12px; font-weight: 800; }
    .stat strong { display: block; margin-top: 4px; font-size: 18px; }
    .detail-layout { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(320px, .65fr); gap: 18px; margin-top: 18px; align-items: start; }
    .timeline { position: relative; display: grid; gap: 14px; margin-bottom: 18px; }
    .event { border-left: 4px solid var(--line); padding-left: 14px; }
    .event.good { border-color: var(--green); }
    .event.warn { border-color: var(--amber); }
    .event-title, .context-path, .item-title { margin: 0 0 5px; font-weight: 900; }
    .excerpt, pre { margin-top: 10px; padding: 11px; overflow: auto; border: 1px solid var(--line); border-radius: 6px; background: #fbfaf4; white-space: pre-wrap; }
    .context-list, .trace-item, .approval-item { display: grid; gap: 12px; }
    .context-item, .trace-item, .approval-item { padding: 12px 0; border-bottom: 1px solid var(--line); }
    .context-item:last-child, .trace-item:last-child, .approval-item:last-child { border-bottom: 0; }
    .legacy-test-labels { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
    @media (max-width: 980px) {
      .dashboard-shell, .detail-layout { grid-template-columns: 1fr; }
      .task-sidebar { border-right: 0; border-bottom: 1px solid var(--line); }
      .section-head, .run-hero-top { flex-direction: column; }
      .stat-band, .evidence-strip { grid-template-columns: 1fr; }
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
    form?.addEventListener("submit", async (event) => {
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
        if (!response.ok) throw new Error(await response.text());
        const result = await response.json();
        if (result.detail_url) window.location.href = result.detail_url;
        else window.location.reload();
      } catch (error) {
        message.textContent = "提交失败：" + error.message;
      }
    });
  </script>"""
