# Scoped re-review package

Base: 7d679c3
Head: 2ea72aa

diff --git a/.superpowers/sdd/2026-07-26-readable-run-reports/task-2-report.md b/.superpowers/sdd/2026-07-26-readable-run-reports/task-2-report.md
index 766397a..d136638 100644
--- a/.superpowers/sdd/2026-07-26-readable-run-reports/task-2-report.md
+++ b/.superpowers/sdd/2026-07-26-readable-run-reports/task-2-report.md
@@ -6,20 +6,35 @@ Implemented focused semantic Markdown rendering in `harness/reports.py`.
 The renderer redacts the report once, produces readable run sections, parses
 action arguments safely, retains JSON export behavior, and limits JSON blocks
 to the final audit-data details section.
 
 Verification:
 
 `python -m pytest tests/test_auth_reports.py::test_report_export_renders_readable_run_sections -q -p no:cacheprovider`
 
 Result: `1 passed in 0.05s`.
 
+## Fix round 2
+
+Root cause: only mapping context rows checked their `file` value for an
+absolute path, and the empty-row condition examined the unfiltered input.
+
+Changes: scalar absolute-path context values are omitted and the context table
+now emits its empty row when every source value is filtered. Focused assertions
+cover scalar filtering and the all-filtered empty result.
+
+Verification:
+
+`python -m pytest tests/test_auth_reports.py::test_report_export_renders_readable_run_sections -q -p no:cacheprovider`
+
+Result: `1 passed in 0.05s`.
+
 ## Fix round 1
 
 Root cause: context rows used the stored `file` value directly, and feedback
 and approval mappings fell back to an incomplete single value or a dictionary
 representation.
 
 Changes: absolute paths are omitted from the context table; feedback and
 approval records now render explicit state/status, reason, and result fields.
 Focused assertions cover both behaviors.
 
diff --git a/harness/reports.py b/harness/reports.py
index 8f47618..4b52665 100644
--- a/harness/reports.py
+++ b/harness/reports.py
@@ -108,31 +108,36 @@ class ReportExporter:
                 summary = self._value(args.get("summary")) if args.get("summary") else ""
             if not summary:
                 summary = self._value(action.get("excerpt"))
         lines.extend((summary or "-", ""))
 
     def _render_context(self, lines: list[str], report: Mapping[str, Any]) -> None:
         self._section(lines, "\u6924\u572d\u6d30\u6e1a\u6fca\u7986\u5bb8\u53c9\u20ac\u8364\u7ca8\u9286\u4fd9")
         context = report.get("selected_context", [])
         lines.append("| \u93c2\u56e6\u6b22 | \u7eeb\u8bf2\u7037 | \u95ab\u590b\u5ae8\u9358\u71b7\u6d1c | \u7487\u52eb\u578e |")
         lines.append("| --- | --- | --- | --- |")
+        rendered = False
         for item in context:
             if isinstance(item, Mapping):
                 if self._is_absolute_path(item.get("file")):
                     continue
                 lines.append("| {} | {} | {} | {} |".format(
                     self._value(item.get("file")), self._value(item.get("type")),
                     self._value(item.get("reason")), self._value(item.get("score")),
                 ))
+                rendered = True
             else:
+                if self._is_absolute_path(item):
+                    continue
                 lines.append(f"| {self._value(item)} | - | - | - |")
-        if not context:
+                rendered = True
+        if not rendered:
             lines.append("| - | - | - | - |")
         lines.append("")
 
     def _render_actions(self, lines: list[str], report: Mapping[str, Any]) -> None:
         self._section(lines, "\u5bb8\u67e5\u20ac\u5909\u7b02\u6d93\u5b2b\u6783")
         actions = report.get("action_trace", [])
         for action in actions:
             if not isinstance(action, Mapping):
                 lines.append(f"- {self._value(action)}")
                 continue
diff --git a/tests/test_auth_reports.py b/tests/test_auth_reports.py
index 755190c..5503d7a 100644
--- a/tests/test_auth_reports.py
+++ b/tests/test_auth_reports.py
@@ -266,20 +266,21 @@ def test_report_export_renders_readable_run_sections():
                 "type": "configuration",
                 "reason": "project dependencies",
                 "score": 0.95,
             },
             {
                 "file": "C:/workspace/project/private.py",
                 "type": "source",
                 "reason": "absolute repository path",
                 "score": 0.5,
             },
+            "C:/workspace/project/scalar-private.py",
         ],
         "action_trace": [
             {"tool": "read_file", "path": "pyproject.toml"},
             {"tool": "finish", "excerpt": "Report complete"},
         ],
         "tool_results": [{"tool": "read_file", "result": "[project]"}],
         "changed_files": ["harness/reports.py"],
         "feedback": [{
             "state": "verified",
             "reason": "The output is easy to scan.",
@@ -302,13 +303,17 @@ def test_report_export_renders_readable_run_sections():
     assert "## 宸查€変笂涓嬫枃" in markdown
     assert "| 鏂囦欢 | 绫诲瀷 | 閫夋嫨鍘熷洜 | 璇勫垎 |" in markdown
     assert "pyproject.toml" in markdown
     assert "## 鍔ㄤ綔杞ㄨ迹" in markdown
     assert "璇诲彇鏂囦欢锛歚" in markdown
     assert "pyproject.toml" in markdown
     assert "## 瀹¤鍘熷鏁版嵁" in markdown
     assert "```json" not in markdown.split("## 瀹¤鍘熷鏁版嵁", 1)[0]
     context_section = markdown.split("## \u5bb8\u67e5\u20ac\u5909\u7b02\u6d93\u5b2b\u6783", 1)[0]
     assert "C:/workspace/project/private.py" not in context_section
+    assert "C:/workspace/project/scalar-private.py" not in context_section
+    empty_context = ReportExporter({"selected_context": ["C:/workspace/project/only-private.py"]}).to_markdown()
+    empty_context_section = empty_context.split("## \u5bb8\u67e5\u20ac\u5909\u7b02\u6d93\u5b2b\u6783", 1)[0]
+    assert "| - | - | - | - |" in empty_context_section
     assert "- state: verified; reason: The output is easy to scan.; result: passed" in markdown
     assert "- status: approved; reason: Ready; result: published" in markdown
     assert json.loads(ReportExporter(report).to_json()) == report
