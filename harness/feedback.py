"""Feedback parsing and repeated-failure decisions."""

from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path
from collections.abc import Sequence

from harness.domain import Feedback, FeedbackCategory, FeedbackSource
from harness.storage import _redact


class FeedbackEngine:
    """Build and compare structured feedback from validation results."""

    def discover_validation_commands(
        self,
        repo_root: Path,
        configured: list[str | Sequence[str]] | None = None,
    ) -> list[str | Sequence[str]]:
        """Prefer configured validation commands, then infer common defaults."""
        if configured:
            return configured

        commands: list[str] = []
        pyproject = repo_root / "pyproject.toml"
        if pyproject.exists():
            pyproject_text = pyproject.read_text(encoding="utf-8")
            commands.append("python -m pytest")
            if "[tool.ruff" in pyproject_text:
                commands.append("ruff check .")
            if "[tool.mypy" in pyproject_text:
                commands.append("mypy .")
            if "[build-system]" in pyproject_text:
                commands.append("python -m build")
        if (repo_root / "package.json").exists():
            commands.append("npm test")
        if (repo_root / "Cargo.toml").exists():
            commands.append("cargo test")
        if (repo_root / "pom.xml").exists():
            commands.append("mvn test")
        return commands

    def run_validation(
        self,
        command: str | Sequence[str],
        cwd: Path,
        timeout_seconds: int = 30,
    ) -> Feedback:
        """Run a validation command and convert its result to structured feedback."""
        command_args = list(command) if not isinstance(command, str) else shlex.split(command)
        command_label = " ".join(command_args)
        try:
            completed = subprocess.run(
                command_args,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            feedback = self.timeout_feedback(command_label, exc.stdout or "", exc.stderr or "")
            feedback.passed = False
            return feedback
        except OSError as exc:
            feedback = Feedback(
                source=FeedbackSource.BUILD.value,
                category=FeedbackCategory.UNKNOWN.value,
                summary=f"Validation command could not start: {command_label}",
                raw_excerpt=self._excerpt(str(exc)),
            )
            feedback.passed = False
            return feedback

        return self.parse_validation_result(
            command=command_label,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def parse_validation_result(
        self,
        command: str,
        exit_code: int,
        stdout: str,
        stderr: str,
        source: str | None = None,
    ) -> Feedback:
        """Convert validation output to a structured Feedback record."""
        output = (stdout or "") + "\n" + (stderr or "")
        source = source or self._source_for_command(command)
        category = self._category_for_output(source, output, exit_code)
        locations = self._locations_for_output(output)
        summary = self._summary_for_output(command, category, locations, exit_code)
        feedback = Feedback(
            source=source,
            category=category,
            summary=summary,
            locations=locations,
            raw_excerpt=self._excerpt(output),
        )
        feedback.passed = exit_code == 0
        return feedback

    def timeout_feedback(self, command: str, stdout: str, stderr: str) -> Feedback:
        """Create structured feedback for a validation timeout."""
        output = (stdout or "") + "\n" + (stderr or "")
        feedback = Feedback(
            source=self._source_for_command(command),
            category=FeedbackCategory.UNKNOWN.value,
            summary=f"Validation command timeout: {command}",
            raw_excerpt=self._excerpt(output),
        )
        feedback.passed = False
        return feedback

    def should_stop_early(self, feedback: list[Feedback]) -> bool:
        """Return True after the same failure category and key location repeats."""
        if len(feedback) < 2:
            return False

        previous, current = feedback[-2], feedback[-1]
        previous_location = self._key_location(previous)
        current_location = self._key_location(current)
        return (
            previous.category == current.category
            and previous.round_index != current.round_index
            and previous_location is not None
            and previous_location == current_location
        )

    def _key_location(self, feedback: Feedback) -> str | None:
        if feedback.locations:
            return feedback.locations[0]
        return None

    def _source_for_command(self, command: str) -> str:
        lower = command.lower()
        if "schema" in lower:
            return FeedbackSource.SCHEMA_VALIDATION.value
        if "guardrail" in lower or "approval" in lower:
            return FeedbackSource.GUARDRAIL.value
        if "pytest" in lower or "test" in lower:
            return FeedbackSource.TEST.value
        if "ruff" in lower or "lint" in lower:
            return FeedbackSource.LINT.value
        if "mypy" in lower or "typecheck" in lower:
            return FeedbackSource.TYPECHECK.value
        if "build" in lower or "mvn" in lower or "cargo" in lower:
            return FeedbackSource.BUILD.value
        return FeedbackSource.BUILD.value

    def _category_for_output(self, source: str, output: str, exit_code: int) -> str:
        if exit_code == 0:
            return FeedbackCategory.UNKNOWN.value
        if source == FeedbackSource.SCHEMA_VALIDATION.value and "invalid" in output.lower():
            return FeedbackCategory.INVALID_ACTION.value
        if "schema" in output.lower() and "invalid" in output.lower():
            return FeedbackCategory.INVALID_ACTION.value
        if "guardrail" in output.lower() or "approval rejected" in output.lower():
            return FeedbackCategory.UNSAFE_ACTION.value
        if "syntaxerror" in output.lower():
            return FeedbackCategory.SYNTAX_ERROR.value
        if "typeerror" in output.lower() or source == FeedbackSource.TYPECHECK.value:
            return FeedbackCategory.TYPE_ERROR.value
        if source == FeedbackSource.LINT.value:
            return FeedbackCategory.STYLE_VIOLATION.value
        if source == FeedbackSource.TEST.value:
            return FeedbackCategory.ASSERTION_FAILURE.value
        return FeedbackCategory.UNKNOWN.value

    def _locations_for_output(self, output: str) -> list[str] | None:
        match = re.search(r"([\w./\\-]+\.py::[\w\[\].:-]+)", output)
        if match:
            return [match.group(1).replace("\\", "/")]
        file_match = re.search(r"([\w./\\-]+\.(?:py|ts|js|java|rs)):(\d+)", output)
        if file_match:
            return [f"{file_match.group(1).replace('\\', '/')}:{file_match.group(2)}"]
        return None

    def _summary_for_output(
        self,
        command: str,
        category: str,
        locations: list[str] | None,
        exit_code: int,
    ) -> str:
        location = f" at {locations[0]}" if locations else ""
        if exit_code == 0:
            return f"{command} passed with {category}{location} (exit {exit_code})"
        return f"{command} failed with {category}{location} (exit {exit_code})"

    def _excerpt(self, output: str, limit: int = 1000) -> str:
        return str(_redact(output.strip()))[:limit]
