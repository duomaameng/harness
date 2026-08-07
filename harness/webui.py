"""Human-facing WebUI for the Harness workbench and run detail pages."""

from __future__ import annotations

import json
from html import escape
from typing import Any

from harness.domain import ApprovalStatus
from harness.service import CoreService


def _render_workbench(
    core: CoreService | None,
    *,
    repositories: list[dict[str, str]] | None = None,
    current_repository_id: str | None = None,
) -> str:
    tasks = core.list_tasks() if core is not None else []
    runs = core.list_runs() if core is not None else []
    latest_run = runs[0] if runs else None
    pending_count = sum(1 for run in runs if run.get("status") == "waiting_approval")
    detail_href = f"/ui/runs/{latest_run['id']}" if latest_run else "#view-detail"
    context_count = 0
    action_count = 0
    feedback_count = 0
    if latest_run:
        run_id = str(latest_run["id"])
        context_count = sum(len(pkg.get("items", [])) for pkg in core.list_context(run_id))
        action_count = len(core.list_actions(run_id))
        feedback_count = len(core.list_feedback(run_id))

    current_repository = next(
        (
            repository for repository in repositories or []
            if repository["id"] == current_repository_id
        ),
        None,
    )
    current_name = (
        current_repository["name"]
        if current_repository is not None
        else core.repo_path.name if core is not None else "No repository selected"
    )
    current_path = (
        current_repository["path"]
        if current_repository is not None
        else str(core.repo_path) if core is not None else "Add a repository to begin."
    )
    sidebar = _render_repository_sidebar(
        repositories, current_repository_id, tasks, runs, core is not None
    ) if repositories is not None else _render_repository_sidebar(
        [{"id": "default", "name": current_name, "path": current_path}], "default", tasks, runs, True
    )

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
      </span>
    </a>
    <nav class="nav-tabs" aria-label="main views">
      <a href="#view-workbench">工作台</a>
      <a href="{escape(detail_href)}">运行详情</a>
    </nav>
  </header>
  <main class="dashboard-workbench">
    <input class="view-toggle" type="radio" name="main-panel" id="view-workbench" checked>
    <input class="view-toggle" type="radio" name="main-panel" id="view-detail">
    <div class="dashboard-shell">
      {sidebar}
      <section class="main-view workbench-view">
        <div class="section-head"><h1 class="workbench-title">工作台</h1></div>
        <section class="panel" id="new-task">
          <div class="panel-header">
            <div>
              <h3 class="panel-title" id="create-task">新建任务</h3>
            </div>
          </div>
          <div class="panel-body">
            <div class="current-repo" aria-label="当前仓库">
              <span class="current-repo-label">当前仓库</span>
              <div class="current-repo-name">{escape(current_name)}</div>
              <div class="current-repo-path">{escape(current_path)}</div>
            </div>
            <form class="task-form" id="task-form">
              <label>描述<textarea class="textarea" name="description" rows="7"></textarea></label>
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
    rendered_version = core.webui_events.run_version(str(core.repo_path), run_id)
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
          </div>
        </div>
        <div class="panel-body">
          {_render_result(run, actions, feedback)}
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
  {_run_detail_refresh_script(run_id, rendered_version)}
</body>
</html>"""


def _render_repository_sidebar(
    repositories: list[dict[str, str]],
    current_repository_id: str | None,
    tasks: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    has_current_repository: bool,
) -> str:
    groups: list[str] = []
    for repository in repositories:
        repository_id = escape(repository["id"])
        active = repository["id"] == current_repository_id
        repository_summary = f"""<div class="repo-title-row"><div class="repo-name-with-path"><h4 class="repo-title">{escape(repository['name'])}</h4><span class="repo-path-tooltip" role="tooltip">{escape(repository['path'])}</span></div><span class="badge">{'current' if active else 'available'}</span></div>"""
        selection = (
            f'<div class="repo-head">{repository_summary}</div>'
            if active
            else f'''<form class="repo-select-form" method="post" action="/ui/repositories/{repository_id}/select">
  <button class="repo-select-card" type="submit">{repository_summary}</button>
</form>'''
        )
        controls = f"""<details class="repo-management-menu">
  <summary aria-label="Repository management" title="Repository management">⋯</summary>
  <div class="repo-management-actions">
    <button type="button" data-repository-action="rename" data-repository-id="{repository_id}" data-repository-name="{escape(repository['name'])}" aria-label="Rename {escape(repository['name'])}">Rename</button>
    <button type="button" data-repository-action="delete" data-repository-id="{repository_id}" data-repository-name="{escape(repository['name'])}" aria-label="Remove {escape(repository['name'])}">Remove</button>
  </div>
</details>"""
        task_list = _render_sidebar_tasks(tasks, runs) if active else ""
        groups.append(f"""<section class="repo-group{' active' if active else ''}" aria-label="repository">
  {selection}{controls}{task_list}</section>""")
    empty_prompt = "" if has_current_repository else '<p class="empty">Add a repository to create or run tasks.</p>'
    return f"""<aside class="task-sidebar">
  <div class="sidebar-head"><p class="eyebrow">Repositories</p></div>
  <button class="btn sidebar-action" type="button" data-repository-picker>+ Add repository</button>
  {empty_prompt}<div class="repo-list">{''.join(groups)}</div>
</aside>{_render_repository_management_dialogs(repositories)}{_render_task_management_dialogs(tasks)}"""


def _render_repository_management_dialogs(repositories: list[dict[str, str]]) -> str:
    default_repository_id = escape(repositories[0]["id"]) if repositories else ""
    return f"""<dialog id="rename-repository-dialog" aria-labelledby="rename-repository-title">
  <form class="repository-json-form dialog-form" method="post" action="/ui/repositories/{default_repository_id}/rename">
    <h3 id="rename-repository-title">Rename repository</h3>
    <label>Repository name<input class="input" name="name" required autofocus></label>
    <div class="button-row"><button class="btn" type="submit">Rename</button><button class="btn secondary" type="button" data-dialog-cancel>Cancel</button></div>
  </form>
</dialog>
<dialog id="delete-repository-dialog" aria-labelledby="delete-repository-title">
  <form class="repository-json-form dialog-form" method="post" action="/ui/repositories/{default_repository_id}/delete">
    <h3 id="delete-repository-title">Remove repository</h3>
    <p>Remove from workbench only. Local files are never deleted.</p>
    <div class="button-row"><button class="btn reject" type="submit">Remove</button><button class="btn secondary" type="button" data-dialog-cancel>Cancel</button></div>
  </form>
</dialog>"""


def _render_task_management_dialogs(tasks: list[dict[str, Any]]) -> str:
    default_task_id = escape(str(tasks[0].get("id") or "")) if tasks else ""
    return f"""<dialog id="rename-task-dialog" aria-labelledby="rename-task-title">
  <form class="task-json-form dialog-form" method="post" action="/ui/tasks/{default_task_id}/rename">
    <h3 id="rename-task-title">Rename task</h3>
    <label>Title<input class="input" name="title" required></label>
    <div class="button-row"><button class="btn" type="submit">Save</button><button class="btn secondary" type="button" data-dialog-cancel>Cancel</button></div>
  </form>
</dialog>
<dialog id="delete-task-dialog" aria-labelledby="delete-task-title">
  <form class="task-json-form dialog-form" method="post" action="/ui/tasks/{default_task_id}/delete">
    <h3 id="delete-task-title">Delete task</h3>
    <p>Harness records are permanently removed but repository files are not deleted.</p>
    <div class="button-row"><button class="btn reject" type="submit">Delete</button><button class="btn secondary" type="button" data-dialog-cancel>Cancel</button></div>
  </form>
</dialog>"""


def _render_sidebar_tasks(tasks: list[dict[str, Any]], runs: list[dict[str, Any]]) -> str:
    runs_by_task: dict[Any, list[dict[str, Any]]] = {}
    for run in runs:
        runs_by_task.setdefault(run.get("task_id"), []).append(run)
    if not tasks:
        return '<p class="empty">还没有任务。</p>'
    items = []
    for task in tasks:
        task_id = str(task.get("id") or "")
        task_runs = runs_by_task.get(task.get("id"), [])
        run = task_runs[-1] if task_runs else None
        status = escape(str((run or {}).get("status") or task.get("status") or "pending"))
        title = escape(str(task.get("title") or "Untitled task"))
        content = f'<span class="badge">{status}</span><h5 class="task-item-title">{title}</h5>'
        controls = ""
        if not any(run.get("status") in {"running", "waiting_approval"} for run in task_runs):
            controls = f"""<details class="task-management-menu">
  <summary aria-label="Task management for {title}" title="Task management">⋯</summary>
  <div class="task-management-actions">
    <button type="button" data-task-action="rename" data-task-id="{escape(task_id)}" data-task-title="{title}" aria-label="Rename {title}">Rename</button>
    <button type="button" data-task-action="delete" data-task-id="{escape(task_id)}" data-task-title="{title}" aria-label="Delete {title}">Delete</button>
  </div>
</details>"""
        if run:
            item = f'<a class="task-item" href="/ui/runs/{escape(str(run.get("id")))}">{content}</a>'
        else:
            item = f'<div class="task-item">{content}</div>'
        items.append(f'<article class="task-item-row">{item}{controls}</article>')
    return "".join(items)


def _render_current_run(
    run: dict[str, Any] | None,
    context_count: int,
    action_count: int,
    feedback_count: int,
) -> str:
    if not run:
        return ""
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


def _render_result(
    run: dict[str, Any],
    actions: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
) -> str:
    finish_summary = _finish_summary(actions)
    if finish_summary:
        return f"""<section class="result-card good" aria-labelledby="result-title">
  <p class="eyebrow">运行结果</p>
  <h3 id="result-title">模型已给出结果</h3>
  <p>{escape(finish_summary)}</p>
</section>"""

    invalid_feedback = next(
        (
            item for item in feedback
            if item.get("source") == "schema_validation"
            or item.get("category") == "invalid_action"
        ),
        None,
    )
    if invalid_feedback:
        summary = str(invalid_feedback.get("summary") or "模型返回的动作格式不符合要求。")
        return f"""<section class="result-card warn" aria-labelledby="result-title">
  <p class="eyebrow">运行结果</p>
  <h3 id="result-title">本次没有生成可用结果</h3>
  <p>模型返回的动作格式不符合要求，Harness 没有执行这个动作。</p>
  <p class="item-meta">{escape(summary)}</p>
  <p class="item-meta">你可以把轮次调高后重试，或让任务描述更明确，例如“先读取 pyproject.toml，再用 finish 返回依赖总结”。</p>
</section>"""

    status = str(run.get("status") or "unknown")
    stop_reason = str(run.get("stop_reason") or "暂无")
    retry_advice = "（建议在新建任务时增加轮次后重试）" if stop_reason == "max_repair_rounds" else ""
    return f"""<section class="result-card" aria-labelledby="result-title">
  <p class="eyebrow">运行结果</p>
  <h3 id="result-title">还没有最终结果</h3>
  <p>当前状态：{escape(status)}；原因：{escape(stop_reason)}。{retry_advice}</p>
  <p class="item-meta">下面的时间线和动作轨迹是调试信息，最终总结会优先显示在这里。</p>
</section>"""


def _finish_summary(actions: list[dict[str, Any]]) -> str | None:
    for action in reversed(actions):
        if action.get("action_type") != "finish":
            continue
        args = _action_args(action)
        summary = args.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
    return None


def _action_args(action: dict[str, Any]) -> dict[str, Any]:
    raw = action.get("args_json")
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


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
  <div class="panel-header"><div><h3 class="panel-title" id="context-title">已选上下文</h3></div></div>
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
  <div class="panel-header"><div><h3 class="panel-title" id="approval-title">待审批</h3></div><span class="badge ready">无待审批</span></div>
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
  <div class="panel-header"><div><h3 class="panel-title" id="approval-title">待审批</h3></div><span class="badge warn">中风险</span></div>
  <div class="panel-body">{body}</div>
</section>"""


def _render_report(report: str) -> str:
    return _panel("Report", "报告", f'<div class="report-markdown">{_render_markdown(report)}</div>')


def _render_markdown(markdown: str) -> str:
    lines = markdown.splitlines()
    rendered: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line:
            index += 1
            continue
        if line == "<details>":
            rendered.append("<details>")
            index += 1
            continue
        if line == "</details>":
            rendered.append("</details>")
            index += 1
            continue
        if line.startswith("<summary>") and line.endswith("</summary>"):
            summary = line.removeprefix("<summary>").removesuffix("</summary>")
            rendered.append(f"<summary>{escape(summary)}</summary>")
            index += 1
            continue
        if line.startswith("```"):
            language = line[3:].strip()
            index += 1
            code: list[str] = []
            while index < len(lines) and not lines[index].startswith("```"):
                code.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            class_name = f' class="language-{escape(language)}"' if language else ""
            rendered.append(f"<pre><code{class_name}>{escape(chr(10).join(code))}</code></pre>")
            continue
        if (
            line.startswith("|")
            and index + 1 < len(lines)
            and _is_markdown_table_separator(lines[index + 1])
        ):
            table_lines = [line]
            index += 2
            while index < len(lines) and lines[index].startswith("|"):
                table_lines.append(lines[index])
                index += 1
            rows = [_markdown_table_row(row) for row in table_lines]
            header = "".join(f"<th>{escape(cell)}</th>" for cell in rows[0])
            body = "".join(
                "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>"
                for row in rows[1:]
            )
            rendered.append(f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>")
            continue
        if line.startswith("#") and len(line) > 1 and line.lstrip("#").startswith(" "):
            level = min(len(line) - len(line.lstrip("#")), 6)
            rendered.append(f"<h{level}>{escape(line[level:].strip())}</h{level}>")
            index += 1
            continue
        if line.startswith("- "):
            items: list[str] = []
            while index < len(lines) and lines[index].startswith("- "):
                items.append(f"<li>{escape(lines[index][2:])}</li>")
                index += 1
            rendered.append(f"<ul>{''.join(items)}</ul>")
            continue
        rendered.append(f"<p>{escape(line)}</p>")
        index += 1
    return "".join(rendered)


def _markdown_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_markdown_table_separator(line: str) -> bool:
    cells = _markdown_table_row(line)
    return bool(cells) and all(cell and set(cell) <= {"-", ":"} for cell in cells)


def _panel(title: str, note: str, body: str) -> str:
    return f"""<section class="panel">
  <div class="panel-header"><div><h3 class="panel-title">{escape(title)}</h3></div></div>
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
    body:has(.dashboard-shell) { height: 100vh; overflow: hidden; }
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
    .dashboard-shell { display: grid; grid-template-columns: 320px minmax(0, 1fr); height: calc(100vh - 67px); overflow: hidden; }
    .task-sidebar { min-height: 0; overflow-y: auto; border-right: 1px solid var(--line); padding: 24px 18px; background: rgba(255,253,247,.62); }
    .sidebar-head, .repo-title-row, .section-head, .panel-header, .run-hero-top { display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; }
    .repo-list { display: grid; gap: 14px; }
    .repo-group, .panel, .run-hero { border: 1px solid var(--line); border-radius: 8px; background: var(--panel); }
    .repo-group { padding: 16px; }
    .repo-group.active { box-shadow: inset 4px 0 0 var(--ink); }
    .repo-select-form { margin: 0; }
    .repo-select-card { display: block; width: 100%; padding: 0; border: 0; background: transparent; color: inherit; text-align: left; cursor: pointer; font: inherit; }
    .repo-select-card:hover .repo-title { text-decoration: underline; }
    .repo-select-card:focus-visible { outline: 2px solid #243f63; outline-offset: 4px; border-radius: 4px; }
    .repo-name-with-path { position: relative; min-width: 0; }
    .repo-path-tooltip { position: absolute; z-index: 2; top: calc(100% + 6px); left: 0; display: none; width: max-content; max-width: 250px; padding: 7px 9px; border: 1px solid var(--line); border-radius: 6px; background: var(--ink); color: var(--panel); font-family: var(--mono); font-size: 12px; font-weight: 700; line-height: 1.35; overflow-wrap: anywhere; box-shadow: 0 8px 20px rgba(21,29,26,.18); }
    .repo-name-with-path:hover .repo-path-tooltip,
    .repo-name-with-path:focus-within .repo-path-tooltip { display: block; }
    .task-sidebar .repository-json-form, .sidebar-action { margin-bottom: 14px; }
    .repo-management-menu { position: relative; margin: 10px 0 14px; }
    .repo-management-menu summary { width: 34px; min-height: 34px; padding: 4px 10px; border: 1px solid var(--line); border-radius: 6px; cursor: pointer; font-weight: 900; list-style: none; }
    .repo-management-menu summary::-webkit-details-marker { display: none; }
    .repo-management-actions { position: absolute; z-index: 1; display: grid; min-width: 140px; margin-top: 6px; padding: 6px; border: 1px solid var(--line); border-radius: 6px; background: var(--panel); box-shadow: 0 8px 20px rgba(21,29,26,.14); }
    .repo-management-actions button { padding: 8px; border: 0; border-radius: 4px; background: transparent; color: var(--ink); text-align: left; cursor: pointer; font: inherit; }
    .repo-management-actions button:hover, .repo-management-actions button:focus-visible { background: var(--paper); }
    dialog { width: min(420px, calc(100vw - 32px)); border: 1px solid var(--line); border-radius: 8px; background: var(--panel); color: var(--ink); box-shadow: 0 24px 60px rgba(21,29,26,.25); }
    dialog::backdrop { background: rgba(21,29,26,.35); }
    .dialog-form { display: grid; gap: 14px; }
    .dialog-form h3, .dialog-form p { margin: 0; }
    .repo-title { margin: 0; font-size: 18px; }
    .repo-path, .current-repo-path, .panel-note, .section-summary, .context-reason, .item-meta, .empty, .task-status-note { color: var(--muted); }
    .repo-path, .current-repo-path, .excerpt, pre { font-family: var(--mono); font-size: 12px; overflow-wrap: anywhere; }
    .task-item-row { display: flex; align-items: center; gap: 10px; border-top: 1px solid var(--line); }
    .task-item { display: block; min-width: 0; flex: 1; padding: 12px 0; color: inherit; text-decoration: none; }
    a.task-item:hover { background: rgba(21,29,26,.04); }
    .task-item-title { margin: 7px 0 0; font-size: 15px; }
    .task-management-menu { margin-left: auto; position: relative; }
    .task-management-menu summary { width: 34px; min-height: 34px; padding: 4px 10px; border: 1px solid var(--line); border-radius: 6px; cursor: pointer; font-weight: 900; list-style: none; }
    .task-management-menu summary::-webkit-details-marker { display: none; }
    .task-management-actions { position: absolute; z-index: 1; right: 0; display: grid; min-width: 140px; margin-top: 6px; padding: 6px; border: 1px solid var(--line); border-radius: 6px; background: var(--panel); box-shadow: 0 8px 20px rgba(21,29,26,.14); }
    .task-management-actions button { padding: 8px; border: 0; border-radius: 4px; background: transparent; color: var(--ink); text-align: left; cursor: pointer; font: inherit; }
    .task-management-actions button:hover, .task-management-actions button:focus-visible { background: var(--paper); }
    .main-view, .detail-shell { min-height: 0; overflow-y: auto; padding: 28px; }
    .section-head { margin-bottom: 18px; }
    .section-head h2 { margin: 0; max-width: 780px; font-size: clamp(30px, 4vw, 52px); line-height: 1; letter-spacing: 0; }
    .workbench-title { margin: 0; font-size: clamp(28px, 3vw, 36px); line-height: 1.1; }
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
    .result-card { margin-bottom: 18px; padding: 18px; border: 1px solid var(--line); border-left: 5px solid var(--ink); border-radius: 8px; background: #fbfaf4; }
    .result-card.good { border-left-color: var(--green); background: var(--green-bg); }
    .result-card.warn { border-left-color: var(--amber); background: var(--amber-bg); }
    .result-card h3 { margin: 0 0 8px; font-size: 24px; }
    .result-card p:last-child { margin-bottom: 0; }
    .report-markdown { overflow-x: auto; }
    .report-markdown h1, .report-markdown h2 { margin: 28px 0 12px; line-height: 1.15; }
    .report-markdown h1 { font-size: 30px; }
    .report-markdown h2 { font-size: 22px; }
    .report-markdown h1:first-child { margin-top: 0; }
    .report-markdown p, .report-markdown ul { margin: 10px 0; }
    .report-markdown ul { padding-left: 22px; }
    .report-markdown table { width: 100%; min-width: 700px; border-collapse: collapse; margin: 14px 0; background: #fffefa; }
    .report-markdown th, .report-markdown td { padding: 11px 12px; border: 1px solid var(--line); text-align: left; vertical-align: top; overflow-wrap: anywhere; }
    .report-markdown th { background: #ede8dc; font-size: 13px; white-space: nowrap; }
    .report-markdown th:first-child, .report-markdown td:first-child { width: 23%; }
    .report-markdown th:nth-child(2), .report-markdown td:nth-child(2) { width: 16%; }
    .report-markdown th:nth-child(3), .report-markdown td:nth-child(3) { width: 51%; }
    .report-markdown th:last-child, .report-markdown td:last-child { width: 10%; text-align: center; }
    .report-markdown details { margin-top: 18px; padding: 12px; border: 1px solid var(--line); border-radius: 6px; background: #fbfaf4; }
    .report-markdown summary { cursor: pointer; font-weight: 800; }
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
      body:has(.dashboard-shell) { height: auto; overflow: visible; }
      .dashboard-shell { height: auto; overflow: visible; }
      .task-sidebar { border-right: 0; border-bottom: 1px solid var(--line); }
      .task-sidebar, .main-view, .detail-shell { overflow: visible; }
      .section-head, .run-hero-top { flex-direction: column; }
      .stat-band, .evidence-strip { grid-template-columns: 1fr; }
    }
  </style>"""


def _run_detail_refresh_script(run_id: str, rendered_version: int) -> str:
    """Reconnect for opaque run refresh hints without maintaining client-side state."""
    safe_run_id = json.dumps(run_id)
    return f"""<script>
    (() => {{
      const runId = {safe_run_id};
      const renderedVersion = {rendered_version};
      const scheme = window.location.protocol === "https:" ? "wss" : "ws";
      const socketUrl = `${{scheme}}://${{window.location.host}}/ui/ws/runs/${{encodeURIComponent(runId)}}`;
      let reloadRequested = false;
      let reconnectDelay = 500;
      const maxReconnectDelay = 5000;

      const connect = () => {{
        const socket = new WebSocket(socketUrl);
        socket.onopen = () => {{ reconnectDelay = 500; }};
        socket.onmessage = (message) => {{
          try {{
            const event = JSON.parse(message.data);
            const snapshotChanged = event.type === "run_snapshot" && event.version !== renderedVersion;
            if ((snapshotChanged || event.type === "run_updated") && !reloadRequested) {{
              reloadRequested = true;
              window.location.reload();
            }}
          }} catch (_) {{
            // Ignore malformed refresh hints; a manual refresh remains available.
          }}
        }};
        socket.onclose = () => {{
          if (reloadRequested) return;
          window.setTimeout(connect, reconnectDelay);
          reconnectDelay = Math.min(reconnectDelay * 2, maxReconnectDelay);
        }};
      }};

      connect();
    }})();
  </script>"""


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
    document.querySelectorAll(".repository-json-form").forEach((repositoryForm) => {
      repositoryForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const response = await fetch(repositoryForm.action, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(Object.fromEntries(new FormData(repositoryForm).entries())),
        });
        if (response.ok) window.location.reload();
      });
    });
    document.querySelectorAll(".task-json-form").forEach((taskForm) => {
      taskForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const response = await fetch(taskForm.action, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(Object.fromEntries(new FormData(taskForm).entries())),
        });
        if (response.ok) window.location.reload();
      });
    });
    document.querySelectorAll("[data-repository-picker]").forEach((button) => {
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          const response = await fetch("/ui/repositories/pick", {method: "POST"});
          if (response.status === 200) window.location.reload();
        } finally {
          button.disabled = false;
        }
      });
    });
    document.querySelectorAll("[data-repository-action]").forEach((button) => {
      button.addEventListener("click", () => {
        const dialog = document.querySelector(`#${button.dataset.repositoryAction}-repository-dialog`);
        const dialogForm = dialog?.querySelector("form");
        if (!dialog || !dialogForm) return;
        dialogForm.action = `/ui/repositories/${button.dataset.repositoryId}/${button.dataset.repositoryAction}`;
        const nameInput = dialogForm.elements.namedItem("name");
        if (nameInput) nameInput.value = button.dataset.repositoryName;
        button.closest("details")?.removeAttribute("open");
        dialog.showModal();
      });
    });
    document.querySelectorAll("[data-task-action]").forEach((button) => {
      button.addEventListener("click", () => {
        const dialog = document.querySelector(`#${button.dataset.taskAction}-task-dialog`);
        const dialogForm = dialog?.querySelector("form");
        if (!dialog || !dialogForm) return;
        dialogForm.action = `/ui/tasks/${button.dataset.taskId}/${button.dataset.taskAction}`;
        const titleInput = dialogForm.elements.namedItem("title");
        if (titleInput) titleInput.value = button.dataset.taskTitle;
        button.closest("details")?.removeAttribute("open");
        dialog.showModal();
      });
    });
    document.querySelectorAll("[data-dialog-cancel]").forEach((button) => {
      button.addEventListener("click", () => button.closest("dialog")?.close());
    });
    document.querySelectorAll('form[action^="/ui/approvals/"]').forEach((approvalForm) => {
      approvalForm.addEventListener("submit", () => {
        approvalForm.querySelectorAll("button").forEach((button) => { button.disabled = true; });
      });
    });
  </script>"""


from harness.webui_routes import include_webui

__all__ = ["include_webui"]
