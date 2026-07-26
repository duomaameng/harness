# Scoped re-review package

Base: 1c07f35
Head: 7d679c3

diff --git a/.superpowers/sdd/2026-07-26-readable-run-reports/task-2-report.md b/.superpowers/sdd/2026-07-26-readable-run-reports/task-2-report.md
index 360a6ce..766397a 100644
--- a/.superpowers/sdd/2026-07-26-readable-run-reports/task-2-report.md
+++ b/.superpowers/sdd/2026-07-26-readable-run-reports/task-2-report.md
@@ -5,10 +5,26 @@ Status: complete
 Implemented focused semantic Markdown rendering in `harness/reports.py`.
 The renderer redacts the report once, produces readable run sections, parses
 action arguments safely, retains JSON export behavior, and limits JSON blocks
 to the final audit-data details section.
 
 Verification:
 
 `python -m pytest tests/test_auth_reports.py::test_report_export_renders_readable_run_sections -q -p no:cacheprovider`
 
 Result: `1 passed in 0.05s`.
+
+## Fix round 1
+
+Root cause: context rows used the stored `file` value directly, and feedback
+and approval mappings fell back to an incomplete single value or a dictionary
+representation.
+
+Changes: absolute paths are omitted from the context table; feedback and
+approval records now render explicit state/status, reason, and result fields.
+Focused assertions cover both behaviors.
+
+Verification:
+
+`python -m pytest tests/test_auth_reports.py::test_report_export_renders_readable_run_sections -q -p no:cacheprovider`
+
+Result: `1 passed in 0.05s`.
diff --git a/harness/reports.py b/harness/reports.py
index dca67fc..8f47618 100644
--- a/harness/reports.py
+++ b/harness/reports.py
@@ -110,20 +110,22 @@ class ReportExporter:
                 summary = self._value(action.get("excerpt"))
         lines.extend((summary or "-", ""))
 
     def _render_context(self, lines: list[str], report: Mapping[str, Any]) -> None:
         self._section(lines, "\u6924\u572d\u6d30\u6e1a\u6fca\u7986\u5bb8\u53c9\u20ac\u8364\u7ca8\u9286\u4fd9")
         context = report.get("selected_context", [])
         lines.append("| \u93c2\u56e6\u6b22 | \u7eeb\u8bf2\u7037 | \u95ab\u590b\u5ae8\u9358\u71b7\u6d1c | \u7487\u52eb\u578e |")
         lines.append("| --- | --- | --- | --- |")
         for item in context:
             if isinstance(item, Mapping):
+                if self._is_absolute_path(item.get("file")):
+                    continue
                 lines.append("| {} | {} | {} | {} |".format(
                     self._value(item.get("file")), self._value(item.get("type")),
                     self._value(item.get("reason")), self._value(item.get("score")),
                 ))
             else:
                 lines.append(f"| {self._value(item)} | - | - | - |")
         if not context:
             lines.append("| - | - | - | - |")
         lines.append("")
 
@@ -147,34 +149,33 @@ class ReportExporter:
         if not actions:
             lines.append("- -")
         lines.append("")
 
     def _render_feedback(self, lines: list[str], report: Mapping[str, Any]) -> None:
         self._section(lines, "\u9a8c\u8bc1\u4e0e\u53cd\u9988")
         feedback = report.get("feedback", [])
         results = report.get("tool_results", [])
         for item in [*feedback, *results]:
             if isinstance(item, Mapping):
-                value = item.get("comment") or item.get("result") or item.get("excerpt") or item
-                lines.append(f"- {self._value(value)}")
+                lines.append(f"- {self._render_record(item)}")
             else:
                 lines.append(f"- {self._value(item)}")
         if not feedback and not results:
             lines.append("- -")
         lines.append("")
 
     def _render_approvals(self, lines: list[str], report: Mapping[str, Any]) -> None:
         self._section(lines, "\u5ba1\u6279\u8bb0\u5f55")
         approvals = report.get("approval_decisions", [])
         for approval in approvals:
             if isinstance(approval, Mapping):
-                lines.append(f"- {self._value(approval.get('status'))}: {self._value(approval.get('reason'))}")
+                lines.append(f"- {self._render_record(approval)}")
             else:
                 lines.append(f"- {self._value(approval)}")
         if not approvals:
             lines.append("- -")
         lines.append("")
 
     def _render_changed_files(self, lines: list[str], report: Mapping[str, Any]) -> None:
         self._section(lines, "\u9354\u3124\u7d94\u675e\u3128\u8ff9")
         files = report.get("changed_files", [])
         for path in files:
@@ -185,10 +186,21 @@ class ReportExporter:
 
     @staticmethod
     def _action_args(action: Mapping[str, Any]) -> Any:
         args = action.get("args")
         if not isinstance(args, str):
             return args
         try:
             return json.loads(args)
         except json.JSONDecodeError:
             return args
+
+    @staticmethod
+    def _is_absolute_path(value: Any) -> bool:
+        return isinstance(value, str) and (value.startswith(("/", "\\")) or bool(re.match(r"^[A-Za-z]:[\\/]", value)))
+
+    def _render_record(self, record: Mapping[str, Any]) -> str:
+        preferred = ("state", "status", "reason", "result", "comment", "excerpt")
+        values = [f"{key}: {self._value(record[key])}" for key in preferred if key in record]
+        if values:
+            return "; ".join(values)
+        return "; ".join(f"{key}: {self._value(value)}" for key, value in record.items()) or "-"
diff --git a/tests/test_auth_reports.py b/tests/test_auth_reports.py
index 8f37fca..755190c 100644
--- a/tests/test_auth_reports.py
+++ b/tests/test_auth_reports.py
@@ -259,38 +259,56 @@ def test_report_export_renders_readable_run_sections():
                     }
                 ],
             }
         ],
         "selected_context": [
             {
                 "file": "pyproject.toml",
                 "type": "configuration",
                 "reason": "project dependencies",
                 "score": 0.95,
-            }
+            },
+            {
+                "file": "C:/workspace/project/private.py",
+                "type": "source",
+                "reason": "absolute repository path",
+                "score": 0.5,
+            },
         ],
         "action_trace": [
             {"tool": "read_file", "path": "pyproject.toml"},
             {"tool": "finish", "excerpt": "Report complete"},
         ],
         "tool_results": [{"tool": "read_file", "result": "[project]"}],
         "changed_files": ["harness/reports.py"],
-        "feedback": [{"comment": "Make the report easy to scan."}],
-        "approval_decisions": [{"status": "approved", "reason": "Ready"}],
+        "feedback": [{
+            "state": "verified",
+            "reason": "The output is easy to scan.",
+            "result": "passed",
+        }],
+        "approval_decisions": [{
+            "status": "approved",
+            "reason": "Ready",
+            "result": "published",
+        }],
         "final_status": "success",
         "stop_reason": "completed",
     }
 
     markdown = ReportExporter(report).to_markdown()
 
     assert "## 杩愯姒傝" in markdown
     assert "## 鏈€缁堢粨璁篳" in markdown
     assert "椤圭洰渚濊禆宸叉€荤粨銆俙" in markdown
     assert "## 宸查€変笂涓嬫枃" in markdown
     assert "| 鏂囦欢 | 绫诲瀷 | 閫夋嫨鍘熷洜 | 璇勫垎 |" in markdown
     assert "pyproject.toml" in markdown
     assert "## 鍔ㄤ綔杞ㄨ迹" in markdown
     assert "璇诲彇鏂囦欢锛歚" in markdown
     assert "pyproject.toml" in markdown
     assert "## 瀹¤鍘熷鏁版嵁" in markdown
     assert "```json" not in markdown.split("## 瀹¤鍘熷鏁版嵁", 1)[0]
+    context_section = markdown.split("## \u5bb8\u67e5\u20ac\u5909\u7b02\u6d93\u5b2b\u6783", 1)[0]
+    assert "C:/workspace/project/private.py" not in context_section
+    assert "- state: verified; reason: The output is easy to scan.; result: passed" in markdown
+    assert "- status: approved; reason: Ready; result: published" in markdown
     assert json.loads(ReportExporter(report).to_json()) == report
