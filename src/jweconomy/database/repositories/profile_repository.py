

from __future__ import annotations

from dataclasses import dataclass

from jweconomy.database.database_manager import DatabaseManager


@dataclass(frozen=True, slots=True)
class PlayerProfile:
    uuid: str
    xuid: str
    username: str
    first_seen: str
    last_seen: str
    play_time: int


class ProfileRepository:


    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    async def upsert_profile(self, uuid: str, xuid: str, username: str) -> None:
        if self._db.type == "mysql":
            await self._db.execute(
                """
                INSERT INTO player_profiles (uuid, xuid, username, first_seen, last_seen)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE 
                    username = ?, 
                    last_seen = CURRENT_TIMESTAMP
                """,
                (uuid, xuid, username, username),
            )
        else:
            await self._db.execute(
                """
                INSERT INTO player_profiles (uuid, xuid, username, first_seen, last_seen)
                VALUES (?, ?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(uuid) DO UPDATE SET 
                    username = excluded.username, 
                    last_seen = datetime('now')
                """,
                (uuid, xuid, username),
            )

    async def batch_upsert_profiles(self, entries: list[tuple[str, str | None, str]]) -> None:
        if not entries:
            return
        if self._db.type == "mysql":
            mysql_entries = []
            for uuid, xuid, username in entries:
                mysql_entries.append((uuid, xuid, username, username))
            await self._db.executemany(
                """
                INSERT INTO player_profiles (uuid, xuid, username, first_seen, last_seen)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE 
                    username = ?, 
                    last_seen = CURRENT_TIMESTAMP
                """,
                mysql_entries,
            )
        else:
            await self._db.executemany(
                """
                INSERT INTO player_profiles (uuid, xuid, username, first_seen, last_seen)
                VALUES (?, ?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(uuid) DO UPDATE SET 
                    username = excluded.username, 
                    last_seen = datetime('now')
                """,
                entries,
            )


    async def get_profile(self, uuid: str) -> PlayerProfile | None:
        row = await self._db.fetchone(
            "SELECT uuid, xuid, username, first_seen, last_seen, play_time FROM player_profiles WHERE uuid = ?",
            (uuid,),
        )
        if row is None:
            return None
        return PlayerProfile(
            uuid=row["uuid"], xuid=row["xuid"], username=row["username"],
            first_seen=row["first_seen"], last_seen=row["last_seen"],
            play_time=row["play_time"],
        )

    async def get_profile_by_name(self, username: str) -> PlayerProfile | None:
        row = await self._db.fetchone(
            "SELECT uuid, xuid, username, first_seen, last_seen, play_time FROM player_profiles WHERE username = ? COLLATE NOCASE",
            (username,),
        )
        if row is None:
            return None
        return PlayerProfile(
            uuid=row["uuid"], xuid=row["xuid"], username=row["username"],
            first_seen=row["first_seen"], last_seen=row["last_seen"],
            play_time=row["play_time"],
        )

    async def get_uuid_by_name(self, username: str) -> str | None:
        return await self._db.fetchval(
            "SELECT uuid FROM player_profiles WHERE username = ? COLLATE NOCASE",
            (username,),
        )
