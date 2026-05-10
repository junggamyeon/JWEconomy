

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import aiosqlite

if TYPE_CHECKING:
    from endstone import Logger


class DatabaseManager:


    def __init__(self, db_path: str, logger: Logger | None = None) -> None:
        self._db_path = db_path
        self._logger = logger
        self._db: aiosqlite.Connection | None = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Database is not connected")
        return self._db

    async def connect(self) -> None:

        try:
            os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
            self._db = await aiosqlite.connect(self._db_path)
            self._db.row_factory = aiosqlite.Row
            await self._db.execute("PRAGMA journal_mode=WAL")
            await self._db.execute("PRAGMA foreign_keys=ON")
            await self._db.execute("PRAGMA busy_timeout=5000")
        except Exception as e:
            if self._logger:
                self._logger.error(f"Failed to open SQLite database: {e}")
            raise

    async def close(self) -> None:

        if self._db:
            await self._db.close()
            self._db = None

    async def execute(self, query: str, params: tuple = ()) -> aiosqlite.Cursor:
        cursor = await self.db.execute(query, params)
        await self.db.commit()
        return cursor

    async def executescript(self, script: str) -> None:
        await self.db.executescript(script)
        await self.db.commit()

    async def executemany(self, query: str, params_list: list[tuple]) -> None:

        await self.db.executemany(query, params_list)
        await self.db.commit()

    async def fetchone(self, query: str, params: tuple = ()) -> aiosqlite.Row | None:

        cursor = await self.db.execute(query, params)
        return await cursor.fetchone()

    async def fetchall(self, query: str, params: tuple = ()) -> list[aiosqlite.Row]:

        cursor = await self.db.execute(query, params)
        return await cursor.fetchall()

    async def fetchval(self, query: str, params: tuple = ()) -> Any:

        cursor = await self.db.execute(query, params)
        row = await cursor.fetchone()
        return row[0] if row else None

    async def execute_in_transaction(self, callback) -> Any:

        async with self.db.cursor() as cursor:
            try:
                await self.db.execute("BEGIN IMMEDIATE")
                result = await callback(cursor)
                await self.db.commit()
                return result
            except Exception:
                await self.db.rollback()
                raise
