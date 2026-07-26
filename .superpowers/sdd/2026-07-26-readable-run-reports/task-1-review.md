# Review package

Base: d4938a6b3dd91f5a46ec8a5bd24500cbfe13060a
Head: 75b6408

75b6408 test: specify readable run report
 tests/test_auth_reports.py | 52 ++++++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 52 insertions(+)
diff --git a/tests/test_auth_reports.py b/tests/test_auth_reports.py
index 0dd066f..8f37fca 100644
--- a/tests/test_auth_reports.py
+++ b/tests/test_auth_reports.py
@@ -235,10 +235,62 @@ def test_report_export_preserves_run_sections():
         "final_status": "success",
         "stop_reason": "completed",
     }
 
     payload = json.loads(ReportExporter(report).to_json())
     markdown = ReportExporter(report).to_markdown()
 
     assert payload == report
     for section in report:
         assert section.replace("_", " ").title() in markdown
+
+
+def test_report_export_renders_readable_run_sections():
+    report = {
+        "task_request": "Summarize the report export",
+        "context_packages": [
+            {
+                "package": "harness",
+                "items": [
+                    {
+                        "file": "pyproject.toml",
+                        "type": "configuration",
+                        "reason": "project dependencies",
+                        "score": 0.95,
+                    }
+                ],
+            }
+        ],
+        "selected_context": [
+            {
+                "file": "pyproject.toml",
+                "type": "configuration",
+                "reason": "project dependencies",
+                "score": 0.95,
+            }
+        ],
+        "action_trace": [
+            {"tool": "read_file", "path": "pyproject.toml"},
+            {"tool": "finish", "excerpt": "Report complete"},
+        ],
+        "tool_results": [{"tool": "read_file", "result": "[project]"}],
+        "changed_files": ["harness/reports.py"],
+        "feedback": [{"comment": "Make the report easy to scan."}],
+        "approval_decisions": [{"status": "approved", "reason": "Ready"}],
+        "final_status": "success",
+        "stop_reason": "completed",
+    }
+
+    markdown = ReportExporter(report).to_markdown()
+
+    assert "## 杩愯姒傝" in markdown
+    assert "## 鏈€缁堢粨璁篳" in markdown
+    assert "椤圭洰渚濊禆宸叉€荤粨銆俙" in markdown
+    assert "## 宸查€変笂涓嬫枃" in markdown
+    assert "| 鏂囦欢 | 绫诲瀷 | 閫夋嫨鍘熷洜 | 璇勫垎 |" in markdown
+    assert "pyproject.toml" in markdown
+    assert "## 鍔ㄤ綔杞ㄨ迹" in markdown
+    assert "璇诲彇鏂囦欢锛歚" in markdown
+    assert "pyproject.toml" in markdown
+    assert "## 瀹¤鍘熷鏁版嵁" in markdown
+    assert "```json" not in markdown.split("## 瀹¤鍘熷鏁版嵁", 1)[0]
+    assert json.loads(ReportExporter(report).to_json()) == report
