from harness.domain import Feedback, FeedbackCategory, FeedbackSource
from harness.feedback import FeedbackEngine


def test_repeated_same_pytest_failure_stops_after_second_occurrence():
    first_failure = Feedback(
        source=FeedbackSource.TEST.value,
        category=FeedbackCategory.ASSERTION_FAILURE.value,
        summary="test_math.py::test_addition failed",
        locations=["tests/test_math.py::test_addition"],
    )
    repeated_failure = Feedback(
        source=FeedbackSource.TEST.value,
        category=FeedbackCategory.ASSERTION_FAILURE.value,
        summary="test_math.py::test_addition failed again",
        locations=["tests/test_math.py::test_addition"],
    )

    engine = FeedbackEngine()

    assert engine.should_stop_early([first_failure, repeated_failure])
