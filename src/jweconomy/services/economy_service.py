

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
    def default_currency(self) -> str:
        return self._config.get("default_currency", "coins")

    @property
    def currencies(self) -> list[str]:
        currencies = self._config.get("currencies", {})
        if not currencies:
            return [self.default_currency]
        return list(currencies.keys())


    def _get_currency_config(self, currency: str | None) -> dict[str, Any]:
        curr = currency or self.default_currency
        currencies = self._config.get("currencies", {})
        if curr in currencies:
            return currencies[curr]

        # Backward compatibility fallback
        old_currency_name = self._config.get("currency_name", "Coins")
        if curr.lower() == old_currency_name.lower() or curr == self.default_currency:
            return {
                "starting_balance": self._config.get("starting_balance", 1000.0),
                "currency_symbol": self._config.get("currency_symbol", "$"),
                "currency_name": self._config.get("currency_name", "Coins"),
                "currency_name_plural": self._config.get("currency_name_plural", "Coins"),
                "max_balance": self._config.get("max_balance", 1_000_000_000.0),
            }

        # Default fallback
        return {
            "starting_balance": 1000.0,
            "currency_symbol": "$",
            "currency_name": curr.capitalize(),
            "currency_name_plural": curr.capitalize() + "s",
            "max_balance": 1_000_000_000.0,
        }

    def get_starting_balance(self, currency: str | None = None) -> float:
        return self._get_currency_config(currency).get("starting_balance", 1000.0)

    def get_max_balance(self, currency: str | None = None) -> float:
        return self._get_currency_config(currency).get("max_balance", 1_000_000_000.0)

    def get_currency_symbol(self, currency: str | None = None) -> str:
        return self._get_currency_config(currency).get("currency_symbol", "$")

    def get_currency_name(self, currency: str | None = None) -> str:
        return self._get_currency_config(currency).get("currency_name", "Coins")

    def get_currency_name_plural(self, currency: str | None = None) -> str:
        return self._get_currency_config(currency).get("currency_name_plural", "Coins")

    @property
    def starting_balance(self) -> float:
        return self.get_starting_balance(self.default_currency)

    @property
    def max_balance(self) -> float:
        return self.get_max_balance(self.default_currency)

    @property
    def min_transaction(self) -> float:
        return self._config.get("min_transaction", 0.01)

    @property
    def transfer_tax_percent(self) -> float:
        return self._config.get("transfer_tax_percent", 0.0)

    @property
    def currency_symbol(self) -> str:
        return self.get_currency_symbol(self.default_currency)

    async def get_balance(self, uuid: str, currency: str | None = None) -> float:
        curr = currency or self.default_currency
        cached = self._cache.get(uuid, curr)
        if cached is not None:
            return cached
        balance = await self._balance_repo.get_balance(uuid, curr)
        if balance is None:
            return 0.0
        self._cache.set(uuid, curr, balance)
        return balance

    async def set_balance(self, uuid: str, amount: float, currency: str | None = None) -> float:
        curr = currency or self.default_currency
        max_bal = self.get_max_balance(curr)
        amount = max(0.0, min(amount, max_bal))
        await self._balance_repo.set_balance(uuid, curr, amount)
        self._cache.set(uuid, curr, amount)
        await self._transaction_repo.record_transaction(
            sender_uuid=None, receiver_uuid=uuid, amount=amount,
            transaction_type="SET", currency=curr, description="Admin balance set",
        )
        return amount

    async def add_balance(self, uuid: str, amount: float, currency: str | None = None) -> float:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        curr = currency or self.default_currency
        current = await self.get_balance(uuid, curr)
        max_bal = self.get_max_balance(curr)
        new_balance = min(current + amount, max_bal)
        actual_add = new_balance - current
        await self._balance_repo.set_balance(uuid, curr, new_balance)
        self._cache.set(uuid, curr, new_balance)
        await self._transaction_repo.record_transaction(
            sender_uuid=None, receiver_uuid=uuid, amount=actual_add,
            transaction_type="GIVE", currency=curr, description="Admin balance give",
        )
        return new_balance

    async def remove_balance(self, uuid: str, amount: float, currency: str | None = None) -> float | None:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        curr = currency or self.default_currency
        result = await self._balance_repo.remove_balance(uuid, curr, amount)
        if result is None:
            return None
        self._cache.set(uuid, curr, result)
        await self._transaction_repo.record_transaction(
            sender_uuid=None, receiver_uuid=uuid, amount=amount,
            transaction_type="TAKE", currency=curr, description="Admin balance take",
        )
        return result

    async def transfer_balance(
        self, sender_uuid: str, receiver_uuid: str, amount: float, currency: str | None = None
    ) -> TransferResult:
        curr = currency or self.default_currency
        symbol = self.get_currency_symbol(curr)
        if amount < self.min_transaction:
            return TransferResult(success=False, error=f"Minimum transfer amount is {symbol}{self.min_transaction}")
        if sender_uuid == receiver_uuid:
            return TransferResult(success=False, error="Cannot transfer to yourself")

        tax_rate = self.transfer_tax_percent / 100.0
        tax_amount = round(amount * tax_rate, 2)

        success = await self._balance_repo.transfer_balance(sender_uuid, receiver_uuid, curr, amount)
        if not success:
            return TransferResult(success=False, error="Insufficient balance")

        if tax_amount > 0:
            await self._balance_repo.remove_balance(receiver_uuid, curr, tax_amount)

        sender_bal = await self._balance_repo.get_balance(sender_uuid, curr) or 0.0
        receiver_bal = await self._balance_repo.get_balance(receiver_uuid, curr) or 0.0
        self._cache.set(sender_uuid, curr, sender_bal)
        self._cache.set(receiver_uuid, curr, receiver_bal)

        await self._transaction_repo.record_transaction(
            sender_uuid=sender_uuid, receiver_uuid=receiver_uuid,
            amount=amount, tax_amount=tax_amount,
            transaction_type="TRANSFER", currency=curr, description="Player transfer",
        )
        return TransferResult(success=True, sender_new_balance=sender_bal, receiver_new_balance=receiver_bal, tax_amount=tax_amount)

    async def initialize_player(self, uuid: str, xuid: str, username: str) -> float:
        await self._profile_repo.upsert_profile(uuid, xuid, username)
        
        # Initialize all configured currencies
        currencies = self._config.get("currencies", {})
        if not currencies:
            currencies = {self.default_currency: {}}

        default_bal = 0.0
        for curr in currencies:
            existing = await self._balance_repo.get_balance(uuid, curr)
            if existing is None:
                start_bal = self.get_starting_balance(curr)
                await self._balance_repo.set_balance(uuid, curr, start_bal)
                bal = start_bal
            else:
                bal = existing
            self._cache.set(uuid, curr, bal)
            if curr == self.default_currency:
                default_bal = bal
        return default_bal

    async def get_top_balances(self, currency: str | None = None, limit: int = 10, offset: int = 0) -> list[dict]:
        curr = currency or self.default_currency
        return await self._balance_repo.get_top_balances(curr, limit, offset)

    async def get_uuid_by_name(self, username: str) -> str | None:
        return await self._profile_repo.get_uuid_by_name(username)

    async def batch_save_balances(self, entries: list[tuple[str, str, float]]) -> None:
        await self._balance_repo.batch_set_balances(entries)
