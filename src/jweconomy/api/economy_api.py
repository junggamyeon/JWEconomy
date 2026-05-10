

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jweconomy.services.economy_service import EconomyService, TransferResult
    from jweconomy.cache.balance_cache import BalanceCache


class EconomyAPI:


    def __init__(self, service: EconomyService, cache: BalanceCache) -> None:
        self._service = service
        self._cache = cache

    async def get_balance(self, uuid: str) -> float:
        return await self._service.get_balance(uuid)

    async def add_balance(self, uuid: str, amount: float) -> float:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        return await self._service.add_balance(uuid, amount)

    async def remove_balance(self, uuid: str, amount: float) -> float | None:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        return await self._service.remove_balance(uuid, amount)

    async def set_balance(self, uuid: str, amount: float) -> float:
        return await self._service.set_balance(uuid, amount)

    async def transfer_balance(self, sender_uuid: str, receiver_uuid: str, amount: float) -> TransferResult:
        return await self._service.transfer_balance(sender_uuid, receiver_uuid, amount)

    async def has_balance(self, uuid: str, amount: float) -> bool:
        balance = await self._service.get_balance(uuid)
        return balance >= amount

    @property
    def currency_symbol(self) -> str:
        return self._service.currency_symbol

    @property
    def currency_name(self) -> str:
        return self._service._config.get("currency_name", "Coins")
