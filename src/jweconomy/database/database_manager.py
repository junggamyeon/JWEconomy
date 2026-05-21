

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import aiosqlite

try:
    import aiomysql
except ImportError:
    aiomysql = None

if TYPE_CHECKING:
    from endstone import Logger


class RowWrapper:
    def __init__(self, data: dict) -> None:
        self._dict = data
        self._keys = list(data.keys())

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            if 0 <= key < len(self._keys):
                return self._dict[self._keys[key]]
            raise IndexError("Row index out of range")
        return self._dict[key]

    def __contains__(self, key: Any) -> bool:
        return key in self._dict

    def get(self, key: Any, default: Any = None) -> Any:
        return self._dict.get(key, default)

    def keys(self) -> Any:
        return self._dict.keys()

    def values(self) -> Any:
        return self._dict.values()

    def items(self) -> Any:
        return self._dict.items()

    def __iter__(self) -> Any:
        return iter(self._dict)

    def __len__(self) -> int:
        return len(self._dict)

    def __repr__(self) -> str:
        return f"RowWrapper({self._dict})"


class CursorWrapper:
    def __init__(self, cursor: Any, is_mysql: bool) -> None:
        self._cursor = cursor
        self._is_mysql = is_mysql

    async def execute(self, query: str, params: tuple = ()) -> Any:
        formatted_query = query
        if self._is_mysql:
            formatted_query = query.replace("?", "%s").replace("COLLATE NOCASE", "").replace("datetime('now')", "CURRENT_TIMESTAMP")
        return await self._cursor.execute(formatted_query, params)

    async def fetchone(self) -> RowWrapper | None:
        row = await self._cursor.fetchone()
        if row is None:
            return None
        if not self._is_mysql:
            return RowWrapper(dict(row))
        return RowWrapper(row)

    async def fetchall(self) -> list[RowWrapper]:
        rows = await self._cursor.fetchall()
        if self._is_mysql:
            return [RowWrapper(r) for r in rows]
        return [RowWrapper(dict(r)) for r in rows]

    @property
    def lastrowid(self) -> Any:
        return self._cursor.lastrowid


class DatabaseManager:
    def __init__(self, db_config: dict[str, Any], data_folder: str, logger: Logger | None = None) -> None:
        self._config = db_config
        self._data_folder = data_folder
        self._logger = logger
        self.type = db_config.get("type", "sqlite")
        self._db: aiosqlite.Connection | None = None
        self._pool: aiomysql.Pool | None = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Database is not connected")
        return self._db

    async def connect(self) -> None:
        if self.type == "mysql":
            if aiomysql is None:
                raise ImportError("aiomysql is required for MySQL support")
            mysql_cfg = self._config.get("mysql", {})
            try:
                self._pool = await aiomysql.create_pool(
                    host=mysql_cfg.get("host", "localhost"),
                    port=mysql_cfg.get("port", 3306),
                    user=mysql_cfg.get("username", "root"),
                    password=mysql_cfg.get("password", ""),
                    db=mysql_cfg.get("database", "jweconomy"),
                    minsize=mysql_cfg.get("pool_min_size", 1),
                    maxsize=mysql_cfg.get("pool_max_size", 10),
                    autocommit=True,
                    cursorclass=aiomysql.DictCursor,
                )
                if self._logger:
                    self._logger.info("Connected to MySQL/MariaDB database pool.")
            except Exception as e:
                if self._logger:
                    self._logger.error(f"Failed to connect to MySQL database: {e}")
                raise
        else:
            filename = self._config.get("filename", "jweconomy.db")
            db_path = os.path.join(self._data_folder, filename)
            try:
                os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
                self._db = await aiosqlite.connect(db_path)
                self._db.row_factory = aiosqlite.Row
                await self._db.execute("PRAGMA journal_mode=WAL")
                await self._db.execute("PRAGMA foreign_keys=ON")
                await self._db.execute("PRAGMA busy_timeout=5000")
                if self._logger:
                    self._logger.info(f"Connected to SQLite database: {db_path}")
            except Exception as e:
                if self._logger:
                    self._logger.error(f"Failed to open SQLite database: {e}")
                raise

    async def close(self) -> None:
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
        if self._db:
            await self._db.close()
            self._db = None

    def _format_query(self, query: str) -> str:
        if self.type == "mysql":
            query = query.replace("?", "%s")
            query = query.replace("COLLATE NOCASE", "")
            query = query.replace("datetime('now')", "CURRENT_TIMESTAMP")
        return query

    async def execute(self, query: str, params: tuple = ()) -> Any:
        query = self._format_query(query)
        if self.type == "mysql":
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    class MockCursor:
                        def __init__(self, lastrowid: Any) -> None:
                            self.lastrowid = lastrowid
                    return MockCursor(cursor.lastrowid)
        else:
            cursor = await self.db.execute(query, params)
            await self._db.commit()
            return cursor

    async def executescript(self, script: str) -> None:
        if self.type == "mysql":
            statements = [s.strip() for s in script.split(";") if s.strip()]
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    for statement in statements:
                        formatted = self._format_query(statement)
                        await cursor.execute(formatted)
        else:
            await self.db.executescript(script)
            await self.db.commit()

    async def executemany(self, query: str, params_list: list[tuple]) -> None:
        query = self._format_query(query)
        if self.type == "mysql":
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.executemany(query, params_list)
        else:
            await self.db.executemany(query, params_list)
            await self._db.commit()

    async def fetchone(self, query: str, params: tuple = ()) -> RowWrapper | None:
        query = self._format_query(query)
        if self.type == "mysql":
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    row = await cursor.fetchone()
                    return RowWrapper(row) if row else None
        else:
            cursor = await self.db.execute(query, params)
            row = await cursor.fetchone()
            return RowWrapper(dict(row)) if row else None

    async def fetchall(self, query: str, params: tuple = ()) -> list[RowWrapper]:
        query = self._format_query(query)
        if self.type == "mysql":
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    rows = await cursor.fetchall()
                    return [RowWrapper(r) for r in rows]
        else:
            cursor = await self.db.execute(query, params)
            rows = await cursor.fetchall()
            return [RowWrapper(dict(r)) for r in rows]

    async def fetchval(self, query: str, params: tuple = ()) -> Any:
        row = await self.fetchone(query, params)
        if not row:
            return None
        return row[0]

    async def execute_in_transaction(self, callback: Any) -> Any:
        if self.type == "mysql":
            async with self._pool.acquire() as conn:
                await conn.begin()
                async with conn.cursor() as cursor:
                    try:
                        wrapper = CursorWrapper(cursor, is_mysql=True)
                        result = await callback(wrapper)
                        await conn.commit()
                        return result
                    except Exception:
                        await conn.rollback()
                        raise
        else:
            async with self.db.cursor() as cursor:
                try:
                    await self.db.execute("BEGIN IMMEDIATE")
                    wrapper = CursorWrapper(cursor, is_mysql=False)
                    result = await callback(wrapper)
                    await self.db.commit()
                    return result
                except Exception:
                    await self._db.rollback()
                    raise

