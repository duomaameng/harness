"""Task request profiling and validation discovery hints."""

from __future__ import annotations

import re

from harness.domain import TaskProfile


_VALIDATIONS = (
    ("tests", r"\btests?\b|\bpytest\b|\bunit tests?\b|\bintegration tests?\b"),
    ("lint", r"\blint(?:ing)?\b|\bruff\b|\bflake8\b|\beslint\b"),
    ("typecheck", r"\btype[- ]?check(?:ing)?\b|\bmypy\b|\bpyright\b"),
    ("build", r"\bbuild(?:ing)?\b|\bcompile\b"),
    ("docker", r"\bdocker\b|\bcontainer(?:ize|isation|ization)?\b"),
    ("cli", r"\bcli\b|\bcommand[- ]line\b"),
    ("api", r"\bapi\b|\bendpoint\b|\brest\b|\bgraphql\b"),
    ("webui", r"\bweb\s*ui\b|\bui\b|\bfrontend\b|\bbrowser\b"),
    ("guardrail", r"\bguardrails?\b|\bsafety boundary\b|\bapproval\b"),
    ("memory", r"\bmemory\b|\bremember\b|\bhistorical decision\b"),
    ("report", r"\breport(?:ing)?\b|\bsummary\b|\brelease notes\b"),
)

_TASK_TYPES = (
    ("bugfix", r"\b(?:fix|bug|broken|regression|error)\b"),
    ("refactor", r"\brefactor(?:ing)?\b|\breorganize\b|\brewrite\b"),
    ("test", r"\b(?:test|coverage)\b"),
    ("docs", r"\b(?:document|documentation|readme)\b"),
    ("config", r"\b(?:config|configuration|setting)\b"),
)

_PATH_RE = re.compile(
    r"(?<![\w.-])(?:[\w.-]+[\\/])+[\w.-]+|"
    r"(?<![\w.-])[\w.-]+\.(?:py|js|ts|java|go|rs|md|toml|json)(?![\w.-])"
)
_SYMBOL_RE = re.compile(
    r"(?<![\w])(?:[A-Z][A-Za-z0-9_]+|[a-z_][A-Za-z0-9_]*\([^)]*\))(?![\w])"
)
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")


class TaskProfiler:
    """Extract stable, explainable hints from natural-language requests."""

    def profile(self, request: str) -> TaskProfile:
        text = request.strip()
        lowered = text.lower()
        keywords = self._keywords(text)
        paths = _PATH_RE.findall(text)
        symbols = _SYMBOL_RE.findall(text)
        modules = list(dict.fromkeys(paths + [
            word for word in keywords
            if word in {
                "harness", "storage", "actions", "profiler", "feedback",
                "context", "runner", "cli", "api", "webui",
            }
        ]))
        validations = [
            name for name, pattern in _VALIDATIONS
            if re.search(pattern, lowered)
        ]

        task_type = "feature"
        for candidate, pattern in _TASK_TYPES:
            if re.search(pattern, lowered):
                task_type = candidate
                break

        reasons: list[str] = []
        if self._cross_repository(lowered):
            reasons.append("cross-repository work")
        if re.search(
            r"\b(?:production|prod|staging|external|remote|cloud)\b.*\b(?:deploy|deployment|rollout)\b|"
            r"\b(?:deploy|deployment|rollout)\b.*\b(?:production|prod|staging|external|remote|cloud)\b|"
            r"\brelease to prod\b",
            lowered,
        ):
            reasons.append("external deployment")
        has_architecture_signal = re.search(
            r"\b(?:architecture|architectural|system design|re-architect)\b", lowered
        )
        if has_architecture_signal and re.search(
            r"\b(?:rewrite|redesign|re-architect|architecture rewrite)\b", lowered
        ) and re.search(
            r"\b(?:large|whole|entire|system[- ]wide)\b|\b(?:from scratch|as a whole)\b",
            lowered,
        ):
            reasons.append("large architecture rewrite")

        return TaskProfile(
            task_type=task_type,
            keywords=keywords,
            symbols=symbols,
            likely_modules=modules,
            validation_requirements=validations,
            out_of_scope=bool(reasons),
            decomposition_reason="; ".join(reasons) if reasons else "",
        )

    @staticmethod
    def _keywords(text: str) -> list[str]:
        return list(dict.fromkeys(word.lower() for word in _WORD_RE.findall(text)))

    @staticmethod
    def _cross_repository(lowered: str) -> bool:
        pattern = (
            r"\b(?:cross[- ]repository|cross[- ]repo|multiple repositories|"
            r"two repositories|different repositories)\b"
        )
        if re.search(pattern, lowered):
            return True
        list_match = re.search(
            r"\b([a-z0-9][a-z0-9_.-]*)\s+and\s+([a-z0-9][a-z0-9_.-]*)\s+"
            r"(?:repositories|repos)\b",
            lowered,
        )
        if list_match and list_match.group(1) != list_match.group(2):
            return True
        names = re.findall(
            r"\b([a-z0-9][a-z0-9_.-]*)\s+(?:repository|repositories|repo|repos)\b",
            lowered,
        )
        return len(set(names)) >= 2
