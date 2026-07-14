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
    "pyproject.toml",
    "poetry.lock",
    "package.json",
    "package-lock.json",
    "Dockerfile",
    "docker-compose.yml",
    "ci.yml",
}

_ALLOWED_VALIDATION_COMMANDS = (
    re.compile(r"^python\s+-m\s+pytest(\s|$)"),
    re.compile(r"^pytest(\s|$)"),
    re.compile(r"^ruff\s+check(\s|$)"),
    re.compile(r"^mypy(\s|$)"),
    re.compile(r"^python\s+-m\s+build(\s|$)"),
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
            return self._evaluate_command(str(args.get("command", "")))

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

        if any(pattern.search(normalized) for pattern in _ALLOWED_VALIDATION_COMMANDS):
            return _allow("Known validation command is allowed.")

        lowered = normalized.lower()
        destructive_or_history = ("rm ", "del ", "rmdir ", "git reset", "git checkout", "git rebase")
        network_or_publish = ("curl ", "wget ", "http://", "https://", "npm publish", "twine upload")
        install = ("pip install", "npm install", "poetry add", "cargo install")

        if any(signal in lowered for signal in destructive_or_history):
            return GuardrailResult(
                status=GuardrailDecision.DENY.value,
                risk_level=GuardrailRisk.HIGH.value,
                reason="Dangerous deletion or git history command is denied.",
            )
        if any(signal in lowered for signal in network_or_publish + install):
            return GuardrailResult(
                status=GuardrailDecision.REQUIRE_APPROVAL.value,
                risk_level=GuardrailRisk.HIGH.value,
                reason="Network, publish, or install command requires approval.",
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
