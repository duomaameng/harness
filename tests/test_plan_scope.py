"""Plan scope checks for the currently completed task."""

from pathlib import Path


def test_task1_branch_does_not_include_future_task_files():
    future_task_files = [
        Path("harness/actions.py"),
        Path("tests/test_actions.py"),
    ]

    assert [path for path in future_task_files if path.exists()] == []


def test_generated_review_diff_packages_are_not_committed():
    review_packages = list(Path(".superpowers/sdd").glob("review-*.diff"))

    assert review_packages == []
