

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from endstone import Logger
    from jweconomy.database.database_manager import DatabaseManager


class SchemaManager:


    def __init__(self, db: DatabaseManager, logger: Logger) -> None:
        self._db = db
        self._logger = logger

    async def create_tables(self) -> None:
        await self._create_player_profiles_table()
        await self._create_balances_table()
        await self._create_transactions_table()

    async def _create_player_profiles_table(self) -> None:
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS player_profiles (
                uuid        TEXT PRIMARY KEY,
                xuid        TEXT UNIQUE,
                username    TEXT NOT NULL,
                first_seen  TEXT NOT NULL DEFAULT (datetime('now')),
                last_seen   TEXT NOT NULL DEFAULT (datetime('now')),
                play_time   INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_profiles_username
                ON player_profiles (username COLLATE NOCASE);

            CREATE INDEX IF NOT EXISTS idx_profiles_xuid
                ON player_profiles (xuid);
        """)

    async def _create_balances_table(self) -> None:
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS balances (
                uuid        TEXT PRIMARY KEY REFERENCES player_profiles(uuid),
                balance     REAL NOT NULL DEFAULT 0.0,
                updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_balances_amount
                ON balances (balance DESC);
        """)

    async def _create_transactions_table(self) -> None:
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS transactions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_uuid     TEXT,
                receiver_uuid   TEXT NOT NULL,
                amount          REAL NOT NULL,
                tax_amount      REAL NOT NULL DEFAULT 0.0,
                transaction_type TEXT NOT NULL,
                description     TEXT,
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (sender_uuid) REFERENCES player_profiles(uuid),
                FOREIGN KEY (receiver_uuid) REFERENCES player_profiles(uuid)
            );

            CREATE INDEX IF NOT EXISTS idx_transactions_sender
                ON transactions (sender_uuid, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_transactions_receiver
                ON transactions (receiver_uuid, created_at DESC);
        """)
