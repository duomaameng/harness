# Review package

Base: 2ea72aa
Head: 91815be

diff --git a/tests/test_service_cli_api.py b/tests/test_service_cli_api.py
index 84ea6ad..0d4b8ec 100644
--- a/tests/test_service_cli_api.py
+++ b/tests/test_service_cli_api.py
@@ -563,20 +563,43 @@ def test_webui_run_detail_shows_human_readable_finish_result(tmp_path):
     task_id = _endpoint(api, "/tasks", "POST")({"title": "Summarize dependencies"})["id"]
     run_id = _endpoint(api, "/tasks/{task_id}/runs", "POST")(task_id, {"max_rounds": 1})["id"]
 
     html = _endpoint(api, "/ui/runs/{run_id}", "GET")(run_id).body.decode("utf-8")
 
     assert 'class="result-card' in html
     assert "运行结果" in html
     assert "Project dependencies are Typer, FastAPI, Uvicorn, and keyring." in html
 
 
+def test_report_endpoint_and_webui_render_readable_completed_run_report(tmp_path):
+    repo = tmp_path / "webui-readable-report-repo"
+    repo.mkdir()
+    service = CoreService(
+        repo,
+        llm=MockLLM([
+            '{"thought_summary":"summarized dependencies","action":"finish",'
+            '"args":{"summary":"Project dependencies are Typer, FastAPI, Uvicorn, and keyring."}}'
+        ]),
+    )
+    api = create_app(service)
+    task_id = _endpoint(api, "/tasks", "POST")({"title": "Summarize dependencies"})["id"]
+    run_id = _endpoint(api, "/tasks/{task_id}/runs", "POST")(task_id, {"max_rounds": 1})["id"]
+
+    report = _endpoint(api, "/runs/{run_id}/report", "GET")(run_id)["content"]
+    html = _endpoint(api, "/ui/runs/{run_id}", "GET")(run_id).body.decode("utf-8")
+
+    for consumer in (report, html):
+        assert "杩愯姒傝" in consumer
+        assert "鏈€缁堢粨璁篳" in consumer
+        assert "```json" not in consumer.split("瀹¤鍘熷鏁版嵁", 1)[0]
+
+
 def test_webui_run_detail_explains_invalid_model_action_as_no_usable_result(tmp_path):
     repo = tmp_path / "webui-invalid-result-repo"
     repo.mkdir()
     service = CoreService(
         repo,
         llm=MockLLM([
             '{"action":"read_and_summarize","file":"pyproject.toml",'
             '"description":"Summarize project dependencies","modify":false}'
         ]),
     )
