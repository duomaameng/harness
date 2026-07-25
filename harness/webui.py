"""Minimal HTML WebUI for run observability and approvals."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from harness.domain import ApprovalStatus
from harness.service import CoreService


def include_webui(
    app: FastAPI,
    service: CoreService | None = None,
    *,
    repo_path: str | Path = ".",
) -> FastAPI:
    """Attach human-facing run detail and approval routes to an API app."""

    if getattr(app.state, "webui_included", False):
        return app

    core = service or getattr(app.state, "core_service", None) or CoreService(repo_path)
    app.state.core_service = core
    app.state.webui_included = True

    @app.get("/ui/runs/{run_id}", response_class=HTMLResponse)
    def run_detail(run_id: str) -> HTMLResponse:
        return HTMLResponse(_render_run_detail(core, run_id))

    @app.post("/ui/approvals/{approval_id}/approve", response_class=HTMLResponse)
    def approve(approval_id: str) -> HTMLResponse:
        approval = core.decide_approval(
            approval_id,
            ApprovalStatus.APPROVED.value,
            decided_by="webui",
        )
        return HTMLResponse(_render_decision("批准", approval))

    @app.post("/ui/approvals/{approval_id}/reject", response_class=HTMLResponse)
    def reject(approval_id: str) -> HTMLResponse:
        approval = core.decide_approval(
            approval_id,
            ApprovalStatus.REJECTED.value,
            decided_by="webui",
        )
        return HTMLResponse(_render_decision("拒绝", approval))

    return app


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
        approval
        for approval in approvals
        if approval.get("status") == ApprovalStatus.PENDING.value
    ]

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Harness WebUI · {escape(str(title))}</title>
  <style>
    :root {{
      --ink: #16201d;
      --muted: #5e6a65;
      --paper: #f7f5ef;
      --panel: #fffdf7;
      --line: #d8d3c5;
      --steel: #31445b;
      --green: #286b4a;
      --green-bg: #dfeee5;
      --amber: #a86612;
      --amber-bg: #f5e7ca;
      --red: #9f342f;
      --red-bg: #f1d7d4;
      --mono: "Cascadia Code", Consolas, monospace;
      --sans: "Bahnschrift", "Aptos", "Segoe UI", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        linear-gradient(90deg, rgba(22, 32, 29, 0.035) 1px, transparent 1px) 0 0 / 32px 32px,
        linear-gradient(rgba(22, 32, 29, 0.03) 1px, transparent 1px) 0 0 / 32px 32px,
        var(--paper);
      font-family: var(--sans);
      line-height: 1.45;
    }}
    .topbar {{
      position: sticky;
      top: 0;
      z-index: 2;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      padding: 14px 28px;
      border-bottom: 1px solid var(--line);
      background: rgba(247, 245, 239, 0.94);
      backdrop-filter: blur(14px);
    }}
    .brand {{ display: flex; align-items: center; gap: 12px; min-width: 0; }}
    .brand-mark {{
      display: grid;
      width: 38px;
      height: 38px;
      place-items: center;
      color: var(--panel);
      background: var(--ink);
      border-radius: 6px;
      font-family: var(--mono);
      font-weight: 800;
    }}
    .brand-title {{ margin: 0; font-size: 17px; font-weight: 800; }}
    .brand-subtitle {{ margin: 1px 0 0; color: var(--muted); font-size: 12px; }}
    .status-strip {{ display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }}
    .badge {{
      display: inline-flex;
      min-height: 26px;
      align-items: center;
      gap: 7px;
      padding: 4px 9px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--panel);
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      white-space: nowrap;
    }}
    .badge::before {{
      content: "";
      width: 7px;
      height: 7px;
      border-radius: 99px;
      background: currentColor;
    }}
    .ready {{ color: var(--green); background: var(--green-bg); }}
    .warn {{ color: var(--amber); background: var(--amber-bg); }}
    .danger {{ color: var(--red); background: var(--red-bg); }}
    main {{ padding: 34px 28px 56px; }}
    .section-head {{
      display: flex;
      gap: 18px;
      align-items: flex-end;
      justify-content: space-between;
      margin-bottom: 18px;
    }}
    .eyebrow {{
      margin: 0 0 8px;
      color: var(--steel);
      font-family: var(--mono);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    h1 {{ margin: 0; max-width: 900px; font-size: 34px; line-height: 1.08; }}
    .summary {{ max-width: 620px; margin: 0; color: var(--muted); }}
    .run-hero {{
      padding: 22px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: 0 18px 50px rgba(22, 32, 29, 0.10);
    }}
    .run-hero p {{ max-width: 920px; color: var(--muted); }}
    .stat-band {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 1px;
      margin-top: 20px;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--line);
    }}
    .stat {{ padding: 14px; background: #fbfaf5; }}
    .stat span {{ display: block; color: var(--muted); font-size: 12px; font-weight: 800; }}
    .stat strong {{ display: block; margin-top: 5px; font-size: 18px; }}
    .detail-layout {{
      display: grid;
      grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.6fr);
      gap: 18px;
      align-items: start;
      margin-top: 18px;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
    }}
    .panel + .panel {{ margin-top: 18px; }}
    .panel-header {{
      display: flex;
      justify-content: space-between;
      gap: 14px;
      padding: 16px 18px;
      border-bottom: 1px solid var(--line);
    }}
    .panel-title {{ margin: 0; font-size: 17px; }}
    .panel-note {{ margin: 3px 0 0; color: var(--muted); font-size: 13px; }}
    .panel-body {{ padding: 18px; }}
    .item {{
      padding: 14px 0;
      border-bottom: 1px solid var(--line);
    }}
    .item:first-child {{ padding-top: 0; }}
    .item:last-child {{ padding-bottom: 0; border-bottom: 0; }}
    .item-title {{ margin: 0 0 5px; font-weight: 800; }}
    .item-meta {{ margin: 0; color: var(--muted); font-size: 13px; }}
    .excerpt {{
      margin-top: 10px;
      padding: 10px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fbfaf5;
      font-family: var(--mono);
      font-size: 12px;
      white-space: pre-wrap;
    }}
    .button-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }}
    .btn {{
      min-height: 34px;
      padding: 7px 12px;
      border: 1px solid var(--ink);
      border-radius: 6px;
      background: var(--ink);
      color: var(--panel);
      font-weight: 800;
      cursor: pointer;
    }}
    .btn.reject {{ border-color: var(--red); background: var(--red); }}
    .empty {{ color: var(--muted); font-size: 13px; }}
    pre {{ margin: 0; white-space: pre-wrap; overflow: auto; }}
    @media (max-width: 900px) {{
      .topbar, .section-head {{ align-items: flex-start; flex-direction: column; }}
      .detail-layout, .stat-band {{ grid-template-columns: 1fr; }}
      main {{ padding: 24px 16px 40px; }}
      h1 {{ font-size: 28px; }}
    }}
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand">
      <div class="brand-mark">H</div>
      <div>
        <p class="brand-title">Harness WebUI</p>
        <p class="brand-subtitle">上下文感知运行工作台</p>
      </div>
    </div>
    <div class="status-strip" aria-label="系统状态">
      <span class="badge ready">服务就绪</span>
      <span class="badge {_status_badge(run.get("status"))}">{escape(str(run.get("status") or "unknown"))}</span>
    </div>
  </header>
  <main>
    <div class="section-head">
      <div>
        <p class="eyebrow">运行详情</p>
        <h1>{escape(str(title))}</h1>
      </div>
      <p class="summary">{escape(str(description))}</p>
    </div>
    <section class="run-hero" aria-labelledby="run-status-title">
      <h2 class="panel-title" id="run-status-title">运行状态</h2>
      <p>本页按原型的审计链路展示一次 harness 运行：上下文、动作、反馈、审批和报告均来自 CoreService。</p>
      <div class="stat-band">
        <div class="stat"><span>状态</span><strong>{escape(str(run.get("status") or "unknown"))}</strong></div>
        <div class="stat"><span>轮次</span><strong>{escape(str(run.get("current_round") or 0))}</strong></div>
        <div class="stat"><span>暂停原因</span><strong>{escape(str(run.get("stop_reason") or "无"))}</strong></div>
        <div class="stat"><span>报告</span><strong>可导出</strong></div>
      </div>
    </section>
    <div class="detail-layout">
      <div>
        {_render_context(context_packages)}
        {_render_actions(actions)}
        {_render_feedback(feedback)}
        {_render_report(report)}
      </div>
      <aside>
        {_render_approvals(pending_approvals)}
      </aside>
    </div>
  </main>
</body>
</html>"""


def _render_context(packages: list[dict[str, Any]]) -> str:
    items: list[str] = []
    for package in packages:
        for item in package.get("items", []):
            metadata = item.get("metadata") or {}
            reason = metadata.get("selection_reason") or item.get("summary") or "由上下文选择器选中。"
            source = item.get("source_path") or item.get("kind") or item.get("id")
            items.append(
                f"""<article class="item">
  <p class="item-title">{escape(str(source))}</p>
  <p class="item-meta">{escape(str(reason))}</p>
</article>"""
            )
    return _panel("已选上下文", "解释这些文件或记忆为何进入提示。", "".join(items) or _empty("暂无上下文。"))


def _render_actions(actions: list[dict[str, Any]]) -> str:
    body = "".join(
        f"""<article class="item">
  <p class="item-title">{escape(str(action.get("action_type") or action.get("type") or "动作"))}</p>
  <p class="item-meta">schema={escape(str(action.get("schema_status") or "unknown"))} · guardrail={escape(str(action.get("guardrail_status") or "unknown"))}</p>
  <div class="excerpt">{escape(_compact(action))}</div>
</article>"""
        for action in actions
    )
    return _panel("动作轨迹", "结构化动作、schema 与护栏状态。", body or _empty("暂无动作。"))


def _render_feedback(feedback: list[dict[str, Any]]) -> str:
    body = "".join(
        f"""<article class="item">
  <p class="item-title">{escape(str(item.get("category") or item.get("source") or "反馈"))}</p>
  <p class="item-meta">{escape(str(item.get("summary") or item.get("message") or item.get("content") or ""))}</p>
</article>"""
        for item in feedback
    )
    return _panel("反馈", "验证输出和修复线索。", body or _empty("暂无反馈。"))


def _render_approvals(approvals: list[dict[str, Any]]) -> str:
    if not approvals:
        return _panel("待审批", "执行前需要人工决策。", _empty("暂无待审批动作。"), badge="ready")

    body = "".join(
        f"""<article class="item">
  <p class="item-title">{escape(str(approval.get("action_type") or "审批请求"))}</p>
  <p class="item-meta">{escape(str(approval.get("reason") or "WebUI 只能批准或拒绝，不能编辑动作内容。"))}</p>
  <div class="excerpt">{escape(_compact(approval.get("action_args") or {}))}</div>
  <div class="button-row">
    <form method="post" action="/ui/approvals/{escape(str(approval.get("id")))}/approve">
      <button class="btn" type="submit">批准</button>
    </form>
    <form method="post" action="/ui/approvals/{escape(str(approval.get("id")))}/reject">
      <button class="btn reject" type="submit">拒绝</button>
    </form>
  </div>
</article>"""
        for approval in approvals
    )
    return _panel("待审批", "执行前需要人工决策。", body, badge="warn")


def _render_report(report: str) -> str:
    return _panel("报告", "Markdown 报告内容已由报告导出器处理。", f'<pre>{escape(report)}</pre>')


def _render_decision(label: str, approval: dict[str, Any]) -> str:
    approval_id = escape(str(approval.get("id") or "unknown"))
    status = escape(str(approval.get("status") or "unknown"))
    return f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>审批已{label}</title></head>
<body><h1>审批已{label}</h1><p>审批 {approval_id} 当前状态：{status}</p></body>
</html>"""


def _panel(title: str, note: str, body: str, *, badge: str | None = None) -> str:
    badge_html = f'<span class="badge {badge}">{title}</span>' if badge else ""
    return f"""<section class="panel" aria-labelledby="{escape(title)}-title">
  <div class="panel-header">
    <div>
      <h2 class="panel-title" id="{escape(title)}-title">{escape(title)}</h2>
      <p class="panel-note">{escape(note)}</p>
    </div>
    {badge_html}
  </div>
  <div class="panel-body">{body}</div>
</section>"""


def _empty(message: str) -> str:
    return f'<p class="empty">{escape(message)}</p>'


def _status_badge(status: Any) -> str:
    if status in {"succeeded", "completed"}:
        return "ready"
    if status in {"waiting_approval", "running"}:
        return "warn"
    if status in {"failed", "rejected"}:
        return "danger"
    return ""


def _compact(value: dict[str, Any]) -> str:
    return ", ".join(
        f"{key}={val}"
        for key, val in value.items()
        if val is not None and val != ""
    )
