"""Process-local, opaque refresh notifications for the WebUI."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import TypedDict


class WebUIEvent(TypedDict):
    """An event that tells a client to refresh without exposing run data."""

    type: str
    run_id: str
    repository: str
    timestamp: str


@dataclass(eq=False)
class _Subscription:
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[WebUIEvent]
    pending: bool = False
    active: bool = True


class WebUIEventHub:
    """Deliver refresh hints to queues owned by their subscribing event loops."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._run_subscriptions: dict[tuple[str, str], set[_Subscription]] = defaultdict(set)
        self._repository_subscriptions: dict[str, set[_Subscription]] = defaultdict(set)

    def subscribe_run(self, repository: str, run_id: str) -> asyncio.Queue[WebUIEvent]:
        subscription = self._new_subscription()
        with self._lock:
            self._run_subscriptions[(repository, run_id)].add(subscription)
        return subscription.queue

    def unsubscribe_run(
        self, repository: str, run_id: str, queue: asyncio.Queue[WebUIEvent]
    ) -> None:
        self._unsubscribe(self._run_subscriptions, (repository, run_id), queue)

    def subscribe_repository(self, repository: str) -> asyncio.Queue[WebUIEvent]:
        subscription = self._new_subscription()
        with self._lock:
            self._repository_subscriptions[repository].add(subscription)
        return subscription.queue

    def unsubscribe_repository(self, repository: str, queue: asyncio.Queue[WebUIEvent]) -> None:
        self._unsubscribe(self._repository_subscriptions, repository, queue)

    def publish_run_update(self, repository: str, run_id: str) -> None:
        """Notify run-detail subscribers; repository broadcasts are added separately."""
        event: WebUIEvent = {
            "type": "run_updated",
            "run_id": run_id,
            "repository": repository,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            subscriptions = []
            for subscription in self._run_subscriptions.get((repository, run_id), ()):
                if subscription.active and not subscription.pending:
                    subscription.pending = True
                    subscriptions.append(subscription)
        for subscription in subscriptions:
            try:
                subscription.loop.call_soon_threadsafe(
                    self._enqueue, subscription, event.copy()
                )
            except RuntimeError:
                self.unsubscribe_run(repository, run_id, subscription.queue)

    @staticmethod
    def _new_subscription() -> _Subscription:
        return _Subscription(
            loop=asyncio.get_running_loop(),
            queue=asyncio.Queue(maxsize=1),
        )

    def _unsubscribe(self, subscriptions: dict, key: object, queue: asyncio.Queue[WebUIEvent]) -> None:
        with self._lock:
            matching = subscriptions.get(key)
            if matching is None:
                return
            for subscription in tuple(matching):
                if subscription.queue is queue:
                    subscription.active = False
                    subscription.pending = False
                    matching.remove(subscription)
            if not matching:
                subscriptions.pop(key, None)

    def _enqueue(self, subscription: _Subscription, event: WebUIEvent) -> None:
        with self._lock:
            subscription.pending = False
            if not subscription.active:
                return
            try:
                subscription.queue.put_nowait(event)
            except asyncio.QueueFull:
                pass
