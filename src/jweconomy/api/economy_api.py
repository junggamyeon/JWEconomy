

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jweconomy.services.economy_service import EconomyService, TransferResult
    from jweconomy.cache.balance_cache import BalanceCache


class EconomyAPI:


    def __init__(self, service: EconomyService, cache: BalanceCache) -> None:
        self._service = service
        self._cache = cache

    async def get_balance(self, uuid: str, currency: str | None = None) -> float:
        return await self._service.get_balance(uuid, currency)

    async def add_balance(self, uuid: str, amount: float, currency: str | None = None) -> float:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        return await self._service.add_balance(uuid, amount, currency)

    async def remove_balance(self, uuid: str, amount: float, currency: str | None = None) -> float | None:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        return await self._service.remove_balance(uuid, amount, currency)

    async def set_balance(self, uuid: str, amount: float, currency: str | None = None) -> float:
        return await self._service.set_balance(uuid, amount, currency)

    async def transfer_balance(self, sender_uuid: str, receiver_uuid: str, amount: float, currency: str | None = None) -> TransferResult:
        return await self._service.transfer_balance(sender_uuid, receiver_uuid, amount, currency)

    async def has_balance(self, uuid: str, amount: float, currency: str | None = None) -> bool:
        balance = await self._service.get_balance(uuid, currency)
        return balance >= amount

    def get_currency_symbol(self, currency: str | None = None) -> str:
        return self._service.get_currency_symbol(currency)

    def get_currency_name(self, currency: str | None = None) -> str:
        return self._service.get_currency_name(currency)

    def get_currency_name_plural(self, currency: str | None = None) -> str:
        return self._service.get_currency_name_plural(currency)

    @property
    def currency_symbol(self) -> str:
        return self._service.currency_symbol

    @property
    def currency_name(self) -> str:
        return self._service.get_currency_name(self._service.default_currency)

