

from __future__ import annotations

import time
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jweconomy.services.economy_service import EconomyService


@dataclass(slots=True)
class CacheEntry:
    balance: float
    dirty: bool = False
    timestamp: float = field(default_factory=time.monotonic)


class BalanceCache:


    def __init__(self, max_size: int = 500, ttl_seconds: float = 300.0) -> None:
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, uuid: str) -> float | None:
        with self._lock:
            entry = self._cache.get(uuid)
            if entry is None:
                return None
            if self._is_expired(entry):
                del self._cache[uuid]
                return None
            self._cache.move_to_end(uuid)
            return entry.balance

    def set(self, uuid: str, balance: float, dirty: bool = False) -> None:
        with self._lock:
            if uuid in self._cache:
                self._cache[uuid].balance = balance
                self._cache[uuid].timestamp = time.monotonic()
                if dirty:
                    self._cache[uuid].dirty = True
                self._cache.move_to_end(uuid)
            else:
                self._cache[uuid] = CacheEntry(balance=balance, dirty=dirty, timestamp=time.monotonic())
                self._evict_if_needed()

    def invalidate(self, uuid: str) -> None:
        with self._lock:
            self._cache.pop(uuid, None)

    def invalidate_all(self) -> None:
        with self._lock:
            self._cache.clear()

    def get_dirty_entries(self) -> list[tuple[str, float]]:
        with self._lock:
            dirty = []
            for uuid, entry in self._cache.items():
                if entry.dirty:
                    dirty.append((uuid, entry.balance))
                    entry.dirty = False
            return dirty

    async def flush_all(self, economy_service: EconomyService) -> None:
        dirty_entries = self.get_dirty_entries()
        if dirty_entries:
            await economy_service.batch_save_balances(dirty_entries)

    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    def _is_expired(self, entry: CacheEntry) -> bool:
        return (time.monotonic() - entry.timestamp) > self._ttl

    def _evict_if_needed(self) -> None:
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)
