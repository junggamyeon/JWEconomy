from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jweconomy.database.database_manager import DatabaseManager


@dataclass(frozen=True, slots=True)
class TransactionRecord:
    id: int
    sender_uuid: str | None
    receiver_uuid: str
    amount: float
    tax_amount: float
    transaction_type: str
    currency: str
    description: str | None
    created_at: str


class TransactionRepository:
    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    async def record_transaction(
        self,
        sender_uuid: str | None,
        receiver_uuid: str,
        amount: float,
        transaction_type: str,
        currency: str,
        description: str | None = None,
        tax_amount: float = 0.0,
    ) -> int:
        cursor = await self._db.execute(
            """
            INSERT INTO transactions (sender_uuid, receiver_uuid, amount, tax_amount, transaction_type, currency, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (sender_uuid, receiver_uuid, amount, tax_amount, transaction_type, currency, description),
        )
        return cursor.lastrowid

    async def get_player_transactions(
        self, uuid: str, currency: str | None = None, limit: int = 20, offset: int = 0
    ) -> list[TransactionRecord]:
        if currency is not None:
            rows = await self._db.fetchall(
                """
                SELECT * FROM transactions
                WHERE (sender_uuid = ? OR receiver_uuid = ?) AND currency = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (uuid, uuid, currency, limit, offset),
            )
        else:
            rows = await self._db.fetchall(
                """
                SELECT * FROM transactions
                WHERE sender_uuid = ? OR receiver_uuid = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (uuid, uuid, limit, offset),
            )
        return [
            TransactionRecord(
                id=r["id"], sender_uuid=r["sender_uuid"],
                receiver_uuid=r["receiver_uuid"], amount=r["amount"],
                tax_amount=r["tax_amount"], transaction_type=r["transaction_type"],
                currency=r["currency"], description=r["description"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    async def get_transaction_count(self, uuid: str, currency: str | None = None) -> int:
        if currency is not None:
            return await self._db.fetchval(
                "SELECT COUNT(*) FROM transactions WHERE (sender_uuid = ? OR receiver_uuid = ?) AND currency = ?",
                (uuid, uuid, currency),
            ) or 0
        return await self._db.fetchval(
            "SELECT COUNT(*) FROM transactions WHERE sender_uuid = ? OR receiver_uuid = ?",
            (uuid, uuid),
        ) or 0
