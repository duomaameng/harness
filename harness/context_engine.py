"""Deterministic context package construction."""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from harness.domain import ContextItem, ContextItemKind, ContextPackage, MemoryKind
from harness.memory import MemoryStore
from harness.repo_index import RepositoryIndex
from harness.storage import HarnessStorage


class ContextEngine:
    """Build auditable context packages from static index data and memory."""

    _SOURCE_PRIORITY = {
        ContextItemKind.CODE_STRUCTURE.value: 0,
        ContextItemKind.TEST_MAPPING.value: 1,
        ContextItemKind.PROJECT_CONVENTION.value: 2,
        ContextItemKind.DECISION_MEMORY.value: 3,
    }

    def __init__(
        self,
        repo_path: str | Path,
        storage: HarnessStorage,
        token_budget: int = 4000,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.storage = storage
        self.token_budget = token_budget
        self.memory_store = MemoryStore(storage)

    def build_package(
        self,
        *,
        task_run_id: str,
        round_index: int,
        task_request: str,
    ) -> ContextPackage:
        keywords = self._keywords(task_request)
        candidates = self._repository_candidates(keywords)
        candidates.extend(self._memory_candidates(keywords))

        scored = sorted(
            candidates,
            key=lambda item: (
                -self._score(item, keywords),
                self._SOURCE_PRIORITY.get(item.kind, 99),
                item.source_path or "",
                item.symbol or "",
                item.summary,
            ),
        )
        selected = self._trim(scored)
        persisted = [self.storage.create_context_item(item) for item in selected]
        package = ContextPackage(
            task_run_id=task_run_id,
            round_index=round_index,
            items=[item.id for item in persisted],
            token_estimate=sum(self._estimate_tokens(item) for item in selected),
            selection_reason=self._package_reason(selected),
        )
        return self.storage.create_context_package(package)

    def _repository_candidates(self, keywords: set[str]) -> list[ContextItem]:
        items = RepositoryIndex(self.repo_path).index()
        return [self._with_selection_reason(item, keywords) for item in items]

    def _memory_candidates(self, keywords: set[str]) -> list[ContextItem]:
        memories_by_id = {}
        for keyword in sorted(keywords):
            for memory in self.memory_store.query(
                repo_path=str(self.repo_path),
                kind=MemoryKind.HISTORICAL_DECISION.value,
                keywords=[keyword],
            ):
                memories_by_id[memory.id] = memory
        memories = list(memories_by_id.values())
        if not memories:
            memories = self.memory_store.query(repo_path=str(self.repo_path), keywords=[])
        candidates = []
        for memory in memories:
            reason = "decision memory matched task keywords"
            candidates.append(ContextItem(
                repo_path=str(self.repo_path),
                kind=ContextItemKind.DECISION_MEMORY.value,
                summary=memory.content,
                content_ref=memory.id,
                metadata={
                    "memory_kind": memory.kind,
                    "confidence": memory.confidence,
                    "selection_reason": reason,
                },
            ))
        return candidates

    def _with_selection_reason(
        self, item: ContextItem, keywords: set[str]
    ) -> ContextItem:
        metadata = dict(item.metadata or {})
        metadata.setdefault("selection_reason", self._reason_for(item, keywords))
        return replace(item, metadata=metadata)

    def _score(self, item: ContextItem, keywords: set[str]) -> int:
        haystack = " ".join(
            part or "" for part in [item.source_path, item.symbol, item.summary, item.content_ref]
        ).lower()
        score = sum(3 for keyword in keywords if keyword in haystack)
        if item.kind == ContextItemKind.TEST_MAPPING.value:
            score += 8
        elif item.kind == ContextItemKind.CODE_STRUCTURE.value:
            score += 6
        elif item.kind == ContextItemKind.PROJECT_CONVENTION.value:
            score += 4
        elif item.kind == ContextItemKind.DECISION_MEMORY.value:
            score += 2
        return score

    def _trim(self, items: list[ContextItem]) -> list[ContextItem]:
        selected: list[ContextItem] = []
        total = 0
        for required_kind in self._SOURCE_PRIORITY:
            item = next((candidate for candidate in items if candidate.kind == required_kind), None)
            if item is not None and item not in selected:
                total = self._append_if_budget_allows(selected, item, total)

        for item in items:
            if item in selected:
                continue
            total = self._append_if_budget_allows(selected, item, total)
        return selected

    def _append_if_budget_allows(
        self, selected: list[ContextItem], item: ContextItem, total: int
    ) -> int:
        estimate = self._estimate_tokens(item)
        if total + estimate <= self.token_budget:
            selected.append(item)
            return total + estimate
        return total

    def _reason_for(self, item: ContextItem, keywords: set[str]) -> str:
        matched = [
            keyword for keyword in sorted(keywords)
            if keyword in " ".join(
                part or "" for part in [item.source_path, item.symbol, item.summary]
            ).lower()
        ]
        if matched:
            return "matched task keyword: " + ", ".join(matched)
        if item.kind == ContextItemKind.PROJECT_CONVENTION.value:
            return f"project convention file: {item.source_path}"
        if item.kind == ContextItemKind.TEST_MAPPING.value:
            return item.metadata.get("selection_reason", "related test mapping") if item.metadata else "related test mapping"
        return "static repository structure"

    def _package_reason(self, items: list[ContextItem]) -> str:
        kinds = sorted({item.kind for item in items})
        return "selected deterministic context by score and priority: " + ", ".join(kinds)

    @staticmethod
    def _estimate_tokens(item: ContextItem) -> int:
        text = " ".join(
            part or "" for part in [
                item.source_path,
                item.symbol,
                item.summary,
                item.content_ref,
                str(item.metadata or ""),
            ]
        )
        return max(1, len(text) // 4)

    @staticmethod
    def _keywords(task_request: str) -> set[str]:
        words = {
            word.lower()
            for word in re.findall(r"[A-Za-z_][A-Za-z0-9_]+", task_request)
            if len(word) > 2
        }
        return words - {"the", "and", "with", "for", "add", "update"}
