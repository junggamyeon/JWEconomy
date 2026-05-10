

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from endstone import Logger
    from jweconomy.database.repositories.balance_repository import BalanceRepository
    from jweconomy.database.repositories.transaction_repository import TransactionRepository
    from jweconomy.database.repositories.profile_repository import ProfileRepository
    from jweconomy.cache.balance_cache import BalanceCache


@dataclass(frozen=True, slots=True)
class TransferResult:
    success: bool
    sender_new_balance: float = 0.0
    receiver_new_balance: float = 0.0
    tax_amount: float = 0.0
    error: str | None = None


class EconomyService:


    def __init__(
        self,
        balance_repo: BalanceRepository,
        transaction_repo: TransactionRepository,
        profile_repo: ProfileRepository,
        cache: BalanceCache,
        config: dict[str, Any],
        logger: Logger,
    ) -> None:
        self._balance_repo = balance_repo
        self._transaction_repo = transaction_repo
        self._profile_repo = profile_repo
        self._cache = cache
        self._config = config
        self._logger = logger

    @property
    def starting_balance(self) -> float:
        return self._config.get("starting_balance", 1000.0)

    @property
    def max_balance(self) -> float:
        return self._config.get("max_balance", 1_000_000_000.0)

    @property
    def min_transaction(self) -> float:
        return self._config.get("min_transaction", 0.01)

    @property
    def transfer_tax_percent(self) -> float:
        return self._config.get("transfer_tax_percent", 0.0)

    @property
    def currency_symbol(self) -> str:
        return self._config.get("currency_symbol", "$")

    async def get_balance(self, uuid: str) -> float:
        cached = self._cache.get(uuid)
        if cached is not None:
            return cached
        balance = await self._balance_repo.get_balance(uuid)
        if balance is None:
            return 0.0
        self._cache.set(uuid, balance)
        return balance

    async def set_balance(self, uuid: str, amount: float) -> float:
        amount = max(0.0, min(amount, self.max_balance))
        await self._balance_repo.set_balance(uuid, amount)
        self._cache.set(uuid, amount)
        await self._transaction_repo.record_transaction(
            sender_uuid=None, receiver_uuid=uuid, amount=amount,
            transaction_type="SET", description="Admin balance set",
        )
        return amount

    async def add_balance(self, uuid: str, amount: float) -> float:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        current = await self.get_balance(uuid)
        new_balance = min(current + amount, self.max_balance)
        actual_add = new_balance - current
        await self._balance_repo.set_balance(uuid, new_balance)
        self._cache.set(uuid, new_balance)
        await self._transaction_repo.record_transaction(
            sender_uuid=None, receiver_uuid=uuid, amount=actual_add,
            transaction_type="GIVE", description="Admin balance give",
        )
        return new_balance

    async def remove_balance(self, uuid: str, amount: float) -> float | None:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        result = await self._balance_repo.remove_balance(uuid, amount)
        if result is None:
            return None
        self._cache.set(uuid, result)
        await self._transaction_repo.record_transaction(
            sender_uuid=None, receiver_uuid=uuid, amount=amount,
            transaction_type="TAKE", description="Admin balance take",
        )
        return result

    async def transfer_balance(
        self, sender_uuid: str, receiver_uuid: str, amount: float
    ) -> TransferResult:
        if amount < self.min_transaction:
            return TransferResult(success=False, error=f"Minimum transfer amount is {self.currency_symbol}{self.min_transaction}")
        if sender_uuid == receiver_uuid:
            return TransferResult(success=False, error="Cannot transfer to yourself")

        tax_rate = self.transfer_tax_percent / 100.0
        tax_amount = round(amount * tax_rate, 2)

        success = await self._balance_repo.transfer_balance(sender_uuid, receiver_uuid, amount)
        if not success:
            return TransferResult(success=False, error="Insufficient balance")

        if tax_amount > 0:
            await self._balance_repo.remove_balance(receiver_uuid, tax_amount)

        sender_bal = await self._balance_repo.get_balance(sender_uuid) or 0.0
        receiver_bal = await self._balance_repo.get_balance(receiver_uuid) or 0.0
        self._cache.set(sender_uuid, sender_bal)
        self._cache.set(receiver_uuid, receiver_bal)

        await self._transaction_repo.record_transaction(
            sender_uuid=sender_uuid, receiver_uuid=receiver_uuid,
            amount=amount, tax_amount=tax_amount,
            transaction_type="TRANSFER", description="Player transfer",
        )
        return TransferResult(success=True, sender_new_balance=sender_bal, receiver_new_balance=receiver_bal, tax_amount=tax_amount)

    async def initialize_player(self, uuid: str, xuid: str, username: str) -> float:
        await self._profile_repo.upsert_profile(uuid, xuid, username)
        existing = await self._balance_repo.get_balance(uuid)
        if existing is None:
            await self._balance_repo.set_balance(uuid, self.starting_balance)
            balance = self.starting_balance
        else:
            balance = existing
        self._cache.set(uuid, balance)
        return balance

    async def get_top_balances(self, limit: int = 10, offset: int = 0) -> list[dict]:
        return await self._balance_repo.get_top_balances(limit, offset)

    async def get_uuid_by_name(self, username: str) -> str | None:
        return await self._profile_repo.get_uuid_by_name(username)

    async def batch_save_balances(self, entries: list[tuple[str, float]]) -> None:
        await self._balance_repo.batch_set_balances(entries)
