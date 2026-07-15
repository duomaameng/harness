"""Feedback parsing and repeated-failure decisions."""

from __future__ import annotations

from harness.domain import Feedback


class FeedbackEngine:
    """Build and compare structured feedback from validation results."""

    def should_stop_early(self, feedback: list[Feedback]) -> bool:
        """Return True after the same failure category and key location repeats."""
        if len(feedback) < 2:
            return False

        previous, current = feedback[-2], feedback[-1]
        previous_location = self._key_location(previous)
        current_location = self._key_location(current)
        return (
            previous.category == current.category
            and previous_location is not None
            and previous_location == current_location
        )

    def _key_location(self, feedback: Feedback) -> str | None:
        if feedback.locations:
            return feedback.locations[0]
        return None
