"""Plan scope checks for generated review artifacts."""

from pathlib import Path


def test_generated_review_diff_packages_are_not_committed():
    review_packages = list(Path(".superpowers/sdd").glob("review-*.diff"))

    assert review_packages == []
