

from __future__ import annotations

from jweconomy.database.database_manager import DatabaseManager


class BalanceRepository:


    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    async def get_balance(self, uuid: str) -> float | None:
        row = await self._db.fetchone(
            "SELECT balance FROM balances WHERE uuid = ?", (uuid,)
        )
        return row["balance"] if row else None

    async def set_balance(self, uuid: str, amount: float) -> None:
        await self._db.execute(
            """
            INSERT INTO balances (uuid, balance, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(uuid) DO UPDATE SET balance = excluded.balance, updated_at = datetime('now')
            """,
            (uuid, amount),
        )

    async def add_balance(self, uuid: str, amount: float) -> float:
        row = await self._db.fetchone(
            "SELECT balance FROM balances WHERE uuid = ?", (uuid,)
        )
        current = row["balance"] if row else 0.0
        new_balance = current + amount
        await self.set_balance(uuid, new_balance)
        return new_balance

    async def remove_balance(self, uuid: str, amount: float) -> float | None:
        row = await self._db.fetchone(
            "SELECT balance FROM balances WHERE uuid = ? AND balance >= ?",
            (uuid, amount),
        )
        if row is None:
            return None
        new_balance = row["balance"] - amount
        await self.set_balance(uuid, new_balance)
        return new_balance

    async def get_top_balances(self, limit: int = 10, offset: int = 0) -> list[dict]:
        rows = await self._db.fetchall(
            """
            SELECT p.uuid, p.username, b.balance
            FROM balances b
            JOIN player_profiles p ON b.uuid = p.uuid
            ORDER BY b.balance DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        return [
            {"uuid": r["uuid"], "username": r["username"], "balance": r["balance"]}
            for r in rows
        ]

    async def transfer_balance(
        self, sender_uuid: str, receiver_uuid: str, amount: float
    ) -> bool:

        async def _transfer(cursor):
            await cursor.execute(
                "SELECT balance FROM balances WHERE uuid = ?", (sender_uuid,)
            )
            sender = await cursor.fetchone()
            if sender is None or sender[0] < amount:
                return False

            await cursor.execute(
                "UPDATE balances SET balance = balance - ?, updated_at = datetime('now') WHERE uuid = ?",
                (amount, sender_uuid),
            )
            await cursor.execute(
                """
                INSERT INTO balances (uuid, balance, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(uuid) DO UPDATE SET balance = balance + excluded.balance, updated_at = datetime('now')
                """,
                (receiver_uuid, amount),
            )
            return True

        return await self._db.execute_in_transaction(_transfer)

    async def exists(self, uuid: str) -> bool:
        val = await self._db.fetchval(
            "SELECT 1 FROM balances WHERE uuid = ?", (uuid,)
        )
        return val is not None

    async def batch_set_balances(self, entries: list[tuple[str, float]]) -> None:
        if not entries:
            return
        await self._db.executemany(
            """
            INSERT INTO balances (uuid, balance, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(uuid) DO UPDATE SET balance = excluded.balance, updated_at = datetime('now')
            """,
            entries,
        )
