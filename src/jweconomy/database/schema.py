from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from endstone import Logger
    from jweconomy.database.database_manager import DatabaseManager


class SchemaManager:
    def __init__(self, db: DatabaseManager, logger: Logger) -> None:
        self._db = db
        self._logger = logger

    async def create_tables(self, default_currency: str = "money") -> None:
        if self._db.type == "mysql":
            await self._create_mysql_tables(default_currency)
        else:
            await self._create_sqlite_tables(default_currency)

    async def _create_sqlite_tables(self, default_currency: str) -> None:
        # Create player_profiles first
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

        # Check if balances table needs migration (does it have a currency column?)
        table_exists = await self._db.fetchval(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='balances'"
        )
        needs_migration = False
        if table_exists:
            columns = await self._db.fetchall("PRAGMA table_info(balances)")
            has_currency = any(col["name"] == "currency" for col in columns)
            if not has_currency:
                needs_migration = True

        if needs_migration:
            self._logger.debug("Migrating SQLite balances table to support multi-currency...")
            await self._db.executescript("""
                ALTER TABLE balances RENAME TO balances_old;
                
                CREATE TABLE balances (
                    uuid        TEXT REFERENCES player_profiles(uuid) ON DELETE CASCADE,
                    currency    TEXT NOT NULL,
                    balance     REAL NOT NULL DEFAULT 0.0,
                    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (uuid, currency)
                );
                
                INSERT INTO balances (uuid, currency, balance, updated_at)
                SELECT uuid, ?, balance, updated_at FROM balances_old;
                
                DROP TABLE balances_old;
            """, (default_currency,))
            self._logger.debug("SQLite balances migration completed successfully.")
        else:
            await self._db.executescript("""
                CREATE TABLE IF NOT EXISTS balances (
                    uuid        TEXT REFERENCES player_profiles(uuid) ON DELETE CASCADE,
                    currency    TEXT NOT NULL,
                    balance     REAL NOT NULL DEFAULT 0.0,
                    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (uuid, currency)
                );

                CREATE INDEX IF NOT EXISTS idx_balances_amount
                    ON balances (balance DESC);
            """)

        # Check transactions table for currency column
        tx_table_exists = await self._db.fetchval(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='transactions'"
        )
        if tx_table_exists:
            columns = await self._db.fetchall("PRAGMA table_info(transactions)")
            has_currency = any(col["name"] == "currency" for col in columns)
            if not has_currency:
                self._logger.debug("Adding currency column to transactions table...")
                await self._db.execute(
                    f"ALTER TABLE transactions ADD COLUMN currency TEXT NOT NULL DEFAULT '{default_currency}'"
                )

        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS transactions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_uuid     TEXT,
                receiver_uuid   TEXT NOT NULL,
                amount          REAL NOT NULL,
                tax_amount      REAL NOT NULL DEFAULT 0.0,
                transaction_type TEXT NOT NULL,
                currency        TEXT NOT NULL,
                description     TEXT,
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (sender_uuid) REFERENCES player_profiles(uuid) ON DELETE SET NULL,
                FOREIGN KEY (receiver_uuid) REFERENCES player_profiles(uuid) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_transactions_sender
                ON transactions (sender_uuid, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_transactions_receiver
                ON transactions (receiver_uuid, created_at DESC);
        """)

    async def _create_mysql_tables(self, default_currency: str) -> None:
        # Create player profiles
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS player_profiles (
                uuid        VARCHAR(36) PRIMARY KEY,
                xuid        VARCHAR(32) UNIQUE,
                username    VARCHAR(64) NOT NULL,
                first_seen  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                play_time   INT NOT NULL DEFAULT 0,
                INDEX idx_profiles_username (username)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Check balances migration
        # Check if table exists
        table_exists = await self._db.fetchval("""
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'balances'
        """)
        needs_migration = False
        if table_exists:
            has_currency = await self._db.fetchval("""
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'balances' AND COLUMN_NAME = 'currency'
            """)
            if not has_currency:
                needs_migration = True

        if needs_migration:
            self._logger.debug("Migrating MySQL balances table to support multi-currency...")
            await self._db.executescript(f"""
                RENAME TABLE balances TO balances_old;
                
                CREATE TABLE balances (
                    uuid        VARCHAR(36) NOT NULL,
                    currency    VARCHAR(32) NOT NULL,
                    balance     DOUBLE NOT NULL DEFAULT 0.0,
                    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (uuid, currency),
                    FOREIGN KEY (uuid) REFERENCES player_profiles(uuid) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                
                INSERT INTO balances (uuid, currency, balance, updated_at)
                SELECT uuid, '{default_currency}', balance, updated_at FROM balances_old;
                
                DROP TABLE balances_old;
            """)
            self._logger.debug("MySQL balances migration completed successfully.")
        else:
            await self._db.executescript("""
                CREATE TABLE IF NOT EXISTS balances (
                    uuid        VARCHAR(36) NOT NULL,
                    currency    VARCHAR(32) NOT NULL,
                    balance     DOUBLE NOT NULL DEFAULT 0.0,
                    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (uuid, currency),
                    FOREIGN KEY (uuid) REFERENCES player_profiles(uuid) ON DELETE CASCADE,
                    INDEX idx_balances_amount (balance DESC)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

        # Check transactions migration
        tx_table_exists = await self._db.fetchval("""
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'transactions'
        """)
        if tx_table_exists:
            has_currency = await self._db.fetchval("""
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'transactions' AND COLUMN_NAME = 'currency'
            """)
            if not has_currency:
                self._logger.debug("Adding currency column to MySQL transactions table...")
                await self._db.execute(
                    f"ALTER TABLE transactions ADD COLUMN currency VARCHAR(32) NOT NULL DEFAULT '{default_currency}'"
                )

        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS transactions (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                sender_uuid     VARCHAR(36),
                receiver_uuid   VARCHAR(36) NOT NULL,
                amount          DOUBLE NOT NULL,
                tax_amount      DOUBLE NOT NULL DEFAULT 0.0,
                transaction_type VARCHAR(32) NOT NULL,
                currency        VARCHAR(32) NOT NULL,
                description     VARCHAR(255),
                created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_uuid) REFERENCES player_profiles(uuid) ON DELETE SET NULL,
                FOREIGN KEY (receiver_uuid) REFERENCES player_profiles(uuid) ON DELETE CASCADE,
                INDEX idx_transactions_sender (sender_uuid, created_at DESC),
                INDEX idx_transactions_receiver (receiver_uuid, created_at DESC)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
