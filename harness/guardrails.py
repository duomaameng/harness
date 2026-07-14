"""Guardrail checks for parsed actions before tool dispatch."""

from __future__ import annotations

import json
import re
from pathlib import Path

from harness.domain import Action, ActionType, GuardrailDecision, GuardrailResult, GuardrailRisk


_SENSITIVE_PATH_PARTS = {
    ".env",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "credentials",
    "credential",
    "secret",
    "secrets",
    "token",
    "key",
}

_APPROVAL_WRITE_NAMES = {
    ".pre-commit-config.yaml",
    "pyproject.toml",
    "poetry.lock",
    "package.json",
    "package-lock.json",
    "requirements.txt",
    "setup.cfg",
    "tox.ini",
    "mypy.ini",
    "Dockerfile",
    "docker-compose.yml",
    "ci.yml",
}

_ALLOWED_VALIDATION_COMMANDS = (
    re.compile(r"^python\s+-m\s+pytest(?:\s|$)"),
    re.compile(r"^pytest(?:\s|$)"),
    re.compile(r"^ruff\s+check(?:\s|$)"),
    re.compile(r"^mypy(?:\s|$)"),
    re.compile(r"^python\s+-m\s+build(?:\s|$)"),
)

_SHELL_CONTROL_PATTERN = re.compile(r"(\&\&|\|\||[;|<>])")
_DANGEROUS_COMMAND_PATTERNS = (
    re.compile(r"^rm(?:\s|$)"),
    re.compile(r"^del(?:\s|$)"),
    re.compile(r"^erase(?:\s|$)"),
    re.compile(r"^unlink(?:\s|$)"),
    re.compile(r"^rmdir(?:\s|$)"),
    re.compile(r"^remove-item(?:\s|$)"),
    re.compile(r"^git\s+reset(?:\s|$)"),
    re.compile(r"^git\s+checkout(?:\s|$)"),
    re.compile(r"^git\s+rebase(?:\s|$)"),
    re.compile(r"^git\s+commit\s+--amend(?:\s|$)"),
    re.compile(r"^git\s+push\s+.*--force(?:\s|$)"),
    re.compile(r"^git\s+filter-branch(?:\s|$)"),
    re.compile(r"^git\s+update-ref(?:\s|$)"),
)
_NETWORK_OR_PUBLISH_PATTERNS = (
    re.compile(r"^curl(?:\s|$)"),
    re.compile(r"^wget(?:\s|$)"),
    re.compile(r"^invoke-webrequest(?:\s|$)"),
    re.compile(r"^iwr(?:\s|$)"),
    re.compile(r"^npm\s+publish(?:\s|$)"),
    re.compile(r"^twine\s+upload(?:\s|$)"),
    re.compile(r"https?://"),
)
_INSTALL_PATTERNS = (
    re.compile(r"^pip(?:3)?\s+install(?:\s|$)"),
    re.compile(r"^python\s+-m\s+pip\s+install(?:\s|$)"),
    re.compile(r"^npm\s+(?:install|i)(?:\s|$)"),
    re.compile(r"^poetry\s+add(?:\s|$)"),
    re.compile(r"^cargo\s+install(?:\s|$)"),
)


class Guardrail:
    """Evaluate parsed actions against repository safety rules."""

    def __init__(self, repo_root: str | Path) -> None:
        self.repo_root = Path(repo_root).resolve()

    def evaluate(self, action: Action) -> GuardrailResult:
        args = self._load_args(action)

        if action.action_type in {
            ActionType.READ_FILE.value,
            ActionType.WRITE_FILE.value,
            ActionType.SEARCH.value,
            ActionType.LIST_FILES.value,
            ActionType.SHOW_DIFF.value,
        }:
            path = args.get("path")
            if isinstance(path, str) and path:
                path_result = self._evaluate_path(path)
                if path_result.status != GuardrailDecision.ALLOW.value:
                    return path_result

        if action.action_type == ActionType.READ_FILE.value:
            path = args.get("path", "")
            if isinstance(path, str) and self._is_sensitive_path(path):
                return GuardrailResult(
                    status=GuardrailDecision.DENY.value,
                    risk_level=GuardrailRisk.HIGH.value,
                    reason="Sensitive credential-like files cannot be read.",
                )

        if action.action_type == ActionType.WRITE_FILE.value:
            path = args.get("path", "")
            if isinstance(path, str):
                path_result = self._evaluate_broad_write_path(path)
                if path_result is not None:
                    return path_result
                if self._is_sensitive_path(path):
                    return GuardrailResult(
                        status=GuardrailDecision.REQUIRE_APPROVAL.value,
                        risk_level=GuardrailRisk.HIGH.value,
                        reason="Writing sensitive credential-like files requires approval.",
                    )
                if Path(path).name in _APPROVAL_WRITE_NAMES:
                    return GuardrailResult(
                        status=GuardrailDecision.REQUIRE_APPROVAL.value,
                        risk_level=GuardrailRisk.MEDIUM.value,
                        reason="Overwriting critical configuration requires approval.",
                    )

        if action.action_type == ActionType.RUN_COMMAND.value:
            command = args.get("command")
            if not isinstance(command, str):
                return GuardrailResult(
                    status=GuardrailDecision.DENY.value,
                    risk_level=GuardrailRisk.MEDIUM.value,
                    reason="Command must be a string before dispatch.",
                )
            return self._evaluate_command(command)

        return _allow("Action passed guardrail checks.")

    def _load_args(self, action: Action) -> dict[str, object]:
        try:
            value = json.loads(action.args_json or "{}")
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    def _evaluate_path(self, raw_path: str) -> GuardrailResult:
        candidate = (self.repo_root / raw_path).resolve()
        if candidate != self.repo_root and self.repo_root not in candidate.parents:
            return GuardrailResult(
                status=GuardrailDecision.DENY.value,
                risk_level=GuardrailRisk.HIGH.value,
                reason="Path is outside the repository root.",
            )
        return _allow("Path stays inside the repository root.")

    def _evaluate_broad_write_path(self, raw_path: str) -> GuardrailResult | None:
        candidate = (self.repo_root / raw_path).resolve()
        if candidate == self.repo_root or raw_path.strip() in {"", ".", "./"}:
            return GuardrailResult(
                status=GuardrailDecision.REQUIRE_APPROVAL.value,
                risk_level=GuardrailRisk.HIGH.value,
                reason="Broad write target requires approval.",
            )
        if candidate.exists() and candidate.is_dir():
            return GuardrailResult(
                status=GuardrailDecision.REQUIRE_APPROVAL.value,
                risk_level=GuardrailRisk.HIGH.value,
                reason="Directory write target requires approval.",
            )
        return None

    def _is_sensitive_path(self, raw_path: str) -> bool:
        parts = {part.lower() for part in Path(raw_path).parts}
        name = Path(raw_path).name.lower()
        if parts & _SENSITIVE_PATH_PARTS:
            return True
        return any(marker in name for marker in ("secret", "credential", "token", "key"))

    def _evaluate_command(self, command: str) -> GuardrailResult:
        normalized = " ".join(command.strip().split())
        if not normalized:
            return GuardrailResult(
                status=GuardrailDecision.DENY.value,
                risk_level=GuardrailRisk.MEDIUM.value,
                reason="Blank commands cannot be dispatched.",
            )

        lowered = normalized.lower()
        if _SHELL_CONTROL_PATTERN.search(lowered):
            return GuardrailResult(
                status=GuardrailDecision.DENY.value,
                risk_level=GuardrailRisk.HIGH.value,
                reason="Shell command chaining or redirection is denied.",
            )

        if any(pattern.search(lowered) for pattern in _DANGEROUS_COMMAND_PATTERNS):
            return GuardrailResult(
                status=GuardrailDecision.DENY.value,
                risk_level=GuardrailRisk.HIGH.value,
                reason="Dangerous deletion or git history command is denied.",
            )

        if any(pattern.search(lowered) for pattern in _ALLOWED_VALIDATION_COMMANDS):
            return _allow("Known validation command is allowed.")

        if any(pattern.search(lowered) for pattern in _NETWORK_OR_PUBLISH_PATTERNS + _INSTALL_PATTERNS):
            return GuardrailResult(
                status=GuardrailDecision.REQUIRE_APPROVAL.value,
                risk_level=GuardrailRisk.HIGH.value,
                reason="Network, publish, or install command requires approval.",
            )

        if " --force" in lowered:
            return GuardrailResult(
                status=GuardrailDecision.REQUIRE_APPROVAL.value,
                risk_level=GuardrailRisk.HIGH.value,
                reason="Force-style command requires approval.",
            )

        return GuardrailResult(
            status=GuardrailDecision.REQUIRE_APPROVAL.value,
            risk_level=GuardrailRisk.MEDIUM.value,
            reason="Non-validation command requires approval.",
        )


def _allow(reason: str) -> GuardrailResult:
    return GuardrailResult(
        status=GuardrailDecision.ALLOW.value,
        risk_level=GuardrailRisk.LOW.value,
        reason=reason,
    )
