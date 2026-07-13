from harness.profiler import TaskProfiler


def test_profiler_marks_cross_repo_deployment_out_of_scope():
    request = (
        "Update the payments repository and the billing repository, then deploy "
        "both services to production."
    )

    profile = TaskProfiler().profile(request)

    assert profile.out_of_scope is True
    assert "cross-repository" in profile.decomposition_reason
    assert "deployment" in profile.decomposition_reason


def test_profiler_discovers_validation_requirements():
    profile = TaskProfiler().profile(
        "Add a CLI API and WebUI change; run tests, lint, typecheck, build, Docker, "
        "guardrail and memory checks, then write a report."
    )

    assert profile.validation_requirements == [
        "tests", "lint", "typecheck", "build", "docker", "cli", "api",
        "webui", "guardrail", "memory", "report",
    ]


def test_profiler_extracts_task_type_paths_symbols_and_modules():
    profile = TaskProfiler().profile(
        "Fix harness/profiler.py and update TaskProfiler.profile() in the API module."
    )

    assert profile.task_type == "bugfix"
    assert "fix" in profile.keywords
    assert "harness/profiler.py" in profile.likely_modules
    assert "TaskProfiler" in profile.symbols
    assert "profile()" in profile.symbols


def test_profiler_marks_large_architecture_rewrite_out_of_scope():
    profile = TaskProfiler().profile("Rewrite the entire system architecture and redesign it.")

    assert profile.out_of_scope is True
    assert "large architecture rewrite" in profile.decomposition_reason


def test_profiler_keeps_scoped_feature_in_scope():
    profile = TaskProfiler().profile("Add a small parser to harness/actions.py.")

    assert profile.task_type == "feature"
    assert profile.out_of_scope is False
    assert profile.decomposition_reason == ""
