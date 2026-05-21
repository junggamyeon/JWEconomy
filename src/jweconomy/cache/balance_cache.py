

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
        self._cache: OrderedDict[tuple[str, str], CacheEntry] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, uuid: str, currency: str) -> float | None:
        key = (uuid, currency)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if self._is_expired(entry):
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return entry.balance

    def set(self, uuid: str, currency: str, balance: float, dirty: bool = False) -> None:
        key = (uuid, currency)
        with self._lock:
            if key in self._cache:
                self._cache[key].balance = balance
                self._cache[key].timestamp = time.monotonic()
                if dirty:
                    self._cache[key].dirty = True
                self._cache.move_to_end(key)
            else:
                self._cache[key] = CacheEntry(balance=balance, dirty=dirty, timestamp=time.monotonic())
                self._evict_if_needed()

    def invalidate(self, uuid: str, currency: str | None = None) -> None:
        with self._lock:
            if currency is not None:
                self._cache.pop((uuid, currency), None)
            else:
                keys_to_remove = [k for k in self._cache.keys() if k[0] == uuid]
                for k in keys_to_remove:
                    self._cache.pop(k, None)

    def invalidate_all(self) -> None:
        with self._lock:
            self._cache.clear()

    def get_dirty_entries(self) -> list[tuple[str, str, float]]:
        with self._lock:
            dirty = []
            for (uuid, currency), entry in self._cache.items():
                if entry.dirty:
                    dirty.append((uuid, currency, entry.balance))
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

