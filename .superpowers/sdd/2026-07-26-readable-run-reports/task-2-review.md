# Review package

Base: 75b6408
Head: 1c07f35

1c07f35 feat: render readable run reports
 .../task-2-report.md                               |  14 +++
 harness/reports.py                                 | 121 ++++++++++++++++++++-
 2 files changed, 133 insertions(+), 2 deletions(-)
diff --git a/.superpowers/sdd/2026-07-26-readable-run-reports/task-2-report.md b/.superpowers/sdd/2026-07-26-readable-run-reports/task-2-report.md
new file mode 100644
index 0000000..360a6ce
--- /dev/null
+++ b/.superpowers/sdd/2026-07-26-readable-run-reports/task-2-report.md
@@ -0,0 +1,14 @@
+# Task 2 Report
+
+Status: complete
+
+Implemented focused semantic Markdown rendering in `harness/reports.py`.
+The renderer redacts the report once, produces readable run sections, parses
+action arguments safely, retains JSON export behavior, and limits JSON blocks
+to the final audit-data details section.
+
+Verification:
+
+`python -m pytest tests/test_auth_reports.py::test_report_export_renders_readable_run_sections -q -p no:cacheprovider`
+
+Result: `1 passed in 0.05s`.
diff --git a/harness/reports.py b/harness/reports.py
index 272b426..dca67fc 100644
--- a/harness/reports.py
+++ b/harness/reports.py
@@ -23,22 +23,28 @@ class ReportExporter:
         self.report = report
 
     def to_json(self) -> str:
         return json.dumps(self._redact(self.report), ensure_ascii=False, indent=2)
 
     export_json = to_json
 
     def to_markdown(self) -> str:
         redacted = self._redact(self.report)
         lines = ["# Harness Run Report", ""]
-        for key, value in redacted.items():
-            lines.extend((f"## {key.replace('_', ' ').title()}", "", self._format(value), ""))
+        self._render_overview(lines, redacted)
+        self._render_conclusion(lines, redacted)
+        self._render_context(lines, redacted)
+        self._render_actions(lines, redacted)
+        self._render_feedback(lines, redacted)
+        self._render_approvals(lines, redacted)
+        self._render_changed_files(lines, redacted)
+        lines.extend(("## \u7039\xa4\ue178\u9358\u71b7\ue750\u93c1\u7248\u5d41", "", "<details>", "<summary>\u7039\xa4\ue178\u9358\u71b7\ue750\u93c1\u7248\u5d41</summary>", "", "```json", json.dumps(redacted, ensure_ascii=False, indent=2), "```", "", "</details>", ""))
         return "\n".join(lines).rstrip() + "\n"
 
     export_markdown = to_markdown
 
     @classmethod
     def _redact(cls, value: Any, key: str | None = None) -> Any:
         if key is not None and cls._is_sensitive_key(key):
             return "[REDACTED]"
         if isinstance(value, Mapping):
             return {str(item_key): cls._redact(item, str(item_key)) for item_key, item in value.items()}
@@ -68,10 +74,121 @@ class ReportExporter:
                 "secret", "credential", "credentials", "private_key", "token",
             }
             or normalized.endswith(("_secret", "_token", "_api_key", "_private_key"))
         )
 
     @staticmethod
     def _format(value: Any) -> str:
         if isinstance(value, (dict, list)):
             return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```"
         return str(value)
+
+    @staticmethod
+    def _section(lines: list[str], title: str) -> None:
+        lines.extend((f"## {title}", ""))
+
+    @staticmethod
+    def _value(value: Any) -> str:
+        return str(value) if value not in (None, "") else "-"
+
+    def _render_overview(self, lines: list[str], report: Mapping[str, Any]) -> None:
+        self._section(lines, "\u6769\u612f\ue511\u59d2\u509d\ue74d")
+        for label, key in (("\u4efb\u52a1", "task_request"), ("\u72b6\u6001", "final_status"), ("\u505c\u6b62\u539f\u56e0", "stop_reason")):
+            if key in report:
+                lines.append(f"- {label}: {self._value(report[key])}")
+        lines.append("")
+
+    def _render_conclusion(self, lines: list[str], report: Mapping[str, Any]) -> None:
+        self._section(lines, "\u93c8\u20ac\u7f01\u5822\u7ca8\u7481\u7bf3")
+        summary = ""
+        for action in report.get("action_trace", []):
+            if not isinstance(action, Mapping) or action.get("tool") != "finish":
+                continue
+            args = self._action_args(action)
+            if isinstance(args, Mapping):
+                summary = self._value(args.get("summary")) if args.get("summary") else ""
+            if not summary:
+                summary = self._value(action.get("excerpt"))
+        lines.extend((summary or "-", ""))
+
+    def _render_context(self, lines: list[str], report: Mapping[str, Any]) -> None:
+        self._section(lines, "\u6924\u572d\u6d30\u6e1a\u6fca\u7986\u5bb8\u53c9\u20ac\u8364\u7ca8\u9286\u4fd9")
+        context = report.get("selected_context", [])
+        lines.append("| \u93c2\u56e6\u6b22 | \u7eeb\u8bf2\u7037 | \u95ab\u590b\u5ae8\u9358\u71b7\u6d1c | \u7487\u52eb\u578e |")
+        lines.append("| --- | --- | --- | --- |")
+        for item in context:
+            if isinstance(item, Mapping):
+                lines.append("| {} | {} | {} | {} |".format(
+                    self._value(item.get("file")), self._value(item.get("type")),
+                    self._value(item.get("reason")), self._value(item.get("score")),
+                ))
+            else:
+                lines.append(f"| {self._value(item)} | - | - | - |")
+        if not context:
+            lines.append("| - | - | - | - |")
+        lines.append("")
+
+    def _render_actions(self, lines: list[str], report: Mapping[str, Any]) -> None:
+        self._section(lines, "\u5bb8\u67e5\u20ac\u5909\u7b02\u6d93\u5b2b\u6783")
+        actions = report.get("action_trace", [])
+        for action in actions:
+            if not isinstance(action, Mapping):
+                lines.append(f"- {self._value(action)}")
+                continue
+            tool = self._value(action.get("tool"))
+            args = self._action_args(action)
+            path = action.get("path") or (args.get("path") if isinstance(args, Mapping) else None)
+            if tool == "read_file" and path:
+                lines.append(f"- \u7487\u8bf2\u5f47\u93c2\u56e6\u6b22\u951b\u6b5a: {path}")
+            elif args:
+                rendered = json.dumps(args, ensure_ascii=False) if isinstance(args, (Mapping, list)) else str(args)
+                lines.append(f"- {tool}: {rendered}")
+            else:
+                lines.append(f"- {tool}: {self._value(action.get('excerpt'))}")
+        if not actions:
+            lines.append("- -")
+        lines.append("")
+
+    def _render_feedback(self, lines: list[str], report: Mapping[str, Any]) -> None:
+        self._section(lines, "\u9a8c\u8bc1\u4e0e\u53cd\u9988")
+        feedback = report.get("feedback", [])
+        results = report.get("tool_results", [])
+        for item in [*feedback, *results]:
+            if isinstance(item, Mapping):
+                value = item.get("comment") or item.get("result") or item.get("excerpt") or item
+                lines.append(f"- {self._value(value)}")
+            else:
+                lines.append(f"- {self._value(item)}")
+        if not feedback and not results:
+            lines.append("- -")
+        lines.append("")
+
+    def _render_approvals(self, lines: list[str], report: Mapping[str, Any]) -> None:
+        self._section(lines, "\u5ba1\u6279\u8bb0\u5f55")
+        approvals = report.get("approval_decisions", [])
+        for approval in approvals:
+            if isinstance(approval, Mapping):
+                lines.append(f"- {self._value(approval.get('status'))}: {self._value(approval.get('reason'))}")
+            else:
+                lines.append(f"- {self._value(approval)}")
+        if not approvals:
+            lines.append("- -")
+        lines.append("")
+
+    def _render_changed_files(self, lines: list[str], report: Mapping[str, Any]) -> None:
+        self._section(lines, "\u9354\u3124\u7d94\u675e\u3128\u8ff9")
+        files = report.get("changed_files", [])
+        for path in files:
+            lines.append(f"- {self._value(path)}")
+        if not files:
+            lines.append("- -")
+        lines.append("")
+
+    @staticmethod
+    def _action_args(action: Mapping[str, Any]) -> Any:
+        args = action.get("args")
+        if not isinstance(args, str):
+            return args
+        try:
+            return json.loads(args)
+        except json.JSONDecodeError:
+            return args
