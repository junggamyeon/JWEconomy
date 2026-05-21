

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jweconomy.database.database_manager import DatabaseManager


class BalanceRepository:
    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    async def get_balance(self, uuid: str, currency: str) -> float | None:
        row = await self._db.fetchone(
            "SELECT balance FROM balances WHERE uuid = ? AND currency = ?", (uuid, currency)
        )
        return row["balance"] if row else None

    async def set_balance(self, uuid: str, currency: str, amount: float) -> None:
        if self._db.type == "mysql":
            await self._db.execute(
                """
                INSERT INTO balances (uuid, currency, balance, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE balance = ?, updated_at = CURRENT_TIMESTAMP
                """,
                (uuid, currency, amount, amount),
            )
        else:
            await self._db.execute(
                """
                INSERT INTO balances (uuid, currency, balance, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(uuid, currency) DO UPDATE SET balance = excluded.balance, updated_at = datetime('now')
                """,
                (uuid, currency, amount),
            )

    async def add_balance(self, uuid: str, currency: str, amount: float) -> float:
        current = await self.get_balance(uuid, currency)
        current_val = current if current is not None else 0.0
        new_balance = current_val + amount
        await self.set_balance(uuid, currency, new_balance)
        return new_balance

    async def remove_balance(self, uuid: str, currency: str, amount: float) -> float | None:
        row = await self._db.fetchone(
            "SELECT balance FROM balances WHERE uuid = ? AND currency = ? AND balance >= ?",
            (uuid, currency, amount),
        )
        if row is None:
            return None
        new_balance = row["balance"] - amount
        await self.set_balance(uuid, currency, new_balance)
        return new_balance

    async def get_top_balances(self, currency: str, limit: int = 10, offset: int = 0) -> list[dict]:
        rows = await self._db.fetchall(
            """
            SELECT p.uuid, p.username, b.balance
            FROM balances b
            JOIN player_profiles p ON b.uuid = p.uuid
            WHERE b.currency = ?
            ORDER BY b.balance DESC
            LIMIT ? OFFSET ?
            """,
            (currency, limit, offset),
        )
        return [
            {"uuid": r["uuid"], "username": r["username"], "balance": r["balance"]}
            for r in rows
        ]

    async def transfer_balance(
        self, sender_uuid: str, receiver_uuid: str, currency: str, amount: float
    ) -> bool:
        async def _transfer(cursor: Any) -> bool:
            await cursor.execute(
                "SELECT balance FROM balances WHERE uuid = ? AND currency = ?", (sender_uuid, currency)
            )
            sender = await cursor.fetchone()
            if sender is None or sender["balance"] < amount:
                return False

            await cursor.execute(
                "UPDATE balances SET balance = balance - ?, updated_at = datetime('now') WHERE uuid = ? AND currency = ?",
                (amount, sender_uuid, currency),
            )
            if self._db.type == "mysql":
                await cursor.execute(
                    """
                    INSERT INTO balances (uuid, currency, balance, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON DUPLICATE KEY UPDATE balance = balance + ?, updated_at = CURRENT_TIMESTAMP
                    """,
                    (receiver_uuid, currency, amount, amount),
                )
            else:
                await cursor.execute(
                    """
                    INSERT INTO balances (uuid, currency, balance, updated_at)
                    VALUES (?, ?, ?, datetime('now'))
                    ON CONFLICT(uuid, currency) DO UPDATE SET balance = balance + excluded.balance, updated_at = datetime('now')
                    """,
                    (receiver_uuid, currency, amount),
                )
            return True

        return await self._db.execute_in_transaction(_transfer)

    async def exists(self, uuid: str, currency: str) -> bool:
        val = await self._db.fetchval(
            "SELECT 1 FROM balances WHERE uuid = ? AND currency = ?", (uuid, currency)
        )
        return val is not None

    async def batch_set_balances(self, entries: list[tuple[str, str, float]]) -> None:
        if not entries:
            return
        if self._db.type == "mysql":
            mysql_entries = [(uuid, curr, amt, amt) for uuid, curr, amt in entries]
            await self._db.executemany(
                """
                INSERT INTO balances (uuid, currency, balance, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE balance = ?, updated_at = CURRENT_TIMESTAMP
                """,
                mysql_entries,
            )
        else:
            await self._db.executemany(
                """
                INSERT INTO balances (uuid, currency, balance, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(uuid, currency) DO UPDATE SET balance = excluded.balance, updated_at = datetime('now')
                """,
                entries,
            )

