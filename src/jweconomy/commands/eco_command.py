from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from endstone import Player
from endstone.command import CommandSender

if TYPE_CHECKING:
    from jweconomy.main import JWEconomy


class EcoCommandHandler:
    def __init__(self, plugin: JWEconomy) -> None:
        self._plugin = plugin

    def handle(self, sender: CommandSender, args: list[str]) -> bool:
        if len(args) == 0:
            self._show_usage(sender)
            return True
        sub = args[0].lower()
        sub_args = args[1:]
        if sub == "give":
            self._handle_give(sender, sub_args)
        elif sub == "take":
            self._handle_take(sender, sub_args)
        elif sub == "set":
            self._handle_set(sender, sub_args)
        elif sub == "top":
            self._handle_top(sender, sub_args)
        elif sub == "reload":
            self._handle_reload(sender)
        elif sub == "import":
            self._handle_import(sender, sub_args)
        else:
            self._show_usage(sender)
        return True

    def _handle_give(self, sender: CommandSender, args: list[str]) -> None:
        if len(args) < 2:
            sender.send_message(self._plugin.message_formatter.format("usage_error", usage="/eco give <player> <amount> [currency]"))
            return
        target_name, amount = args[0], self._parse_amount(sender, args[1])
        if amount is None:
            return
        
        service = self._plugin.economy_service
        currency = service.default_currency
        if len(args) >= 3:
            currency_arg = args[2]
            matched_currency = None
            for c in service.currencies:
                if c.lower() == currency_arg.lower():
                    matched_currency = c
                    break
            if matched_currency is None:
                sender.send_message(f"§cInvalid currency. Available: {', '.join(service.currencies)}")
                return
            currency = matched_currency

        async def task():
            try:
                symbol = service.get_currency_symbol(currency)
                target_uuid = await service.get_uuid_by_name(target_name)
                if target_uuid is None:
                    self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message(self._plugin.message_formatter.format("balance_not_found")))
                    return
                await service.add_balance(target_uuid, amount, currency)
                def callback():
                    formatted = self._plugin.message_formatter.format_amount(amount, symbol)
                    sender.send_message(self._plugin.message_formatter.format("eco_give", symbol=symbol, amount=formatted, player=target_name))
                self._plugin.server.scheduler.run_task(self._plugin, callback)
            except Exception as e:
                self._plugin.logger.error(f"Error in eco give: {e}")
                self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message(self._plugin.message_formatter.format("error_generic")))
        self._plugin.run_async(task())

    def _handle_take(self, sender: CommandSender, args: list[str]) -> None:
        if len(args) < 2:
            sender.send_message(self._plugin.message_formatter.format("usage_error", usage="/eco take <player> <amount> [currency]"))
            return
        target_name, amount = args[0], self._parse_amount(sender, args[1])
        if amount is None:
            return
        
        service = self._plugin.economy_service
        currency = service.default_currency
        if len(args) >= 3:
            currency_arg = args[2]
            matched_currency = None
            for c in service.currencies:
                if c.lower() == currency_arg.lower():
                    matched_currency = c
                    break
            if matched_currency is None:
                sender.send_message(f"§cInvalid currency. Available: {', '.join(service.currencies)}")
                return
            currency = matched_currency

        async def task():
            try:
                symbol = service.get_currency_symbol(currency)
                target_uuid = await service.get_uuid_by_name(target_name)
                if target_uuid is None:
                    self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message(self._plugin.message_formatter.format("balance_not_found")))
                    return
                result = await service.remove_balance(target_uuid, amount, currency)
                def callback():
                    if result is None:
                        sender.send_message(self._plugin.message_formatter.format("pay_insufficient"))
                        return
                    formatted = self._plugin.message_formatter.format_amount(amount, symbol)
                    sender.send_message(self._plugin.message_formatter.format("eco_take", symbol=symbol, amount=formatted, player=target_name))
                self._plugin.server.scheduler.run_task(self._plugin, callback)
            except Exception as e:
                self._plugin.logger.error(f"Error in eco take: {e}")
                self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message(self._plugin.message_formatter.format("error_generic")))
        self._plugin.run_async(task())

    def _handle_set(self, sender: CommandSender, args: list[str]) -> None:
        if len(args) < 2:
            sender.send_message(self._plugin.message_formatter.format("usage_error", usage="/eco set <player> <amount> [currency]"))
            return
        target_name = args[0]
        try:
            amount = float(args[1])
        except ValueError:
            sender.send_message(self._plugin.message_formatter.format("pay_invalid_amount"))
            return
        if amount < 0:
            sender.send_message(self._plugin.message_formatter.format("pay_invalid_amount"))
            return
        
        service = self._plugin.economy_service
        currency = service.default_currency
        if len(args) >= 3:
            currency_arg = args[2]
            matched_currency = None
            for c in service.currencies:
                if c.lower() == currency_arg.lower():
                    matched_currency = c
                    break
            if matched_currency is None:
                sender.send_message(f"§cInvalid currency. Available: {', '.join(service.currencies)}")
                return
            currency = matched_currency

        async def task():
            try:
                symbol = service.get_currency_symbol(currency)
                target_uuid = await service.get_uuid_by_name(target_name)
                if target_uuid is None:
                    self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message(self._plugin.message_formatter.format("balance_not_found")))
                    return
                new_balance = await service.set_balance(target_uuid, amount, currency)
                def callback():
                    formatted = self._plugin.message_formatter.format_amount(new_balance, symbol)
                    sender.send_message(self._plugin.message_formatter.format("eco_set", symbol=symbol, amount=formatted, player=target_name))
                self._plugin.server.scheduler.run_task(self._plugin, callback)
            except Exception as e:
                self._plugin.logger.error(f"Error in eco set: {e}")
                self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message(self._plugin.message_formatter.format("error_generic")))
        self._plugin.run_async(task())

    def _handle_top(self, sender: CommandSender, args: list[str]) -> None:
        service = self._plugin.economy_service
        currencies = service.currencies
        
        page = 1
        currency = service.default_currency
        
        if len(args) >= 1:
            arg0 = args[0]
            matched_currency = None
            for c in currencies:
                if c.lower() == arg0.lower():
                    matched_currency = c
                    break
            
            if matched_currency is not None:
                currency = matched_currency
                if len(args) >= 2:
                    try:
                        page = max(1, int(args[1]))
                    except ValueError:
                        pass
            else:
                try:
                    page = max(1, int(arg0))
                except ValueError:
                    pass
                if len(args) >= 2:
                    arg1 = args[1]
                    for c in currencies:
                        if c.lower() == arg1.lower():
                            currency = c
                            break

        async def task():
            try:
                symbol = service.get_currency_symbol(currency)
                per_page = self._plugin._config_loader.economy_config.get("top_entries_per_page", 10)
                offset = (page - 1) * per_page
                entries = await service.get_top_balances(currency, per_page, offset)
                def callback():
                    if not entries:
                        sender.send_message(self._plugin.message_formatter.format("eco_top_empty"))
                        return
                    # Capitalize currency header
                    header = f"§6§l--- Richest Players ({currency.upper()}) ---§r"
                    sender.send_message(header)
                    for i, entry in enumerate(entries):
                        rank = offset + i + 1
                        formatted = self._plugin.message_formatter.format_amount(entry["balance"], symbol)
                        sender.send_message(self._plugin.message_formatter.format("eco_top_entry", rank=rank, player=entry["username"], symbol=symbol, amount=formatted))
                self._plugin.server.scheduler.run_task(self._plugin, callback)
            except Exception as e:
                self._plugin.logger.error(f"Error in eco top: {e}")
                self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message(self._plugin.message_formatter.format("error_generic")))
        self._plugin.run_async(task())

    def _handle_reload(self, sender: CommandSender) -> None:
        try:
            self._plugin._config_loader.reload()
            self._plugin._message_formatter.reload(self._plugin._config_loader.messages)
            sender.send_message(self._plugin.message_formatter.format("eco_reload"))
        except Exception as e:
            self._plugin.logger.error(f"Error reloading config: {e}")
            sender.send_message(self._plugin.message_formatter.format("error_generic"))

    def _handle_import(self, sender: CommandSender, args: list[str]) -> None:
        if not sender.has_permission("jweconomy.admin"):
            sender.send_message(self._plugin.message_formatter.format("no_permission"))
            return
        if len(args) == 0:
            sender.send_message("§cUsage: /eco import mysql <host> <port> <database> <username> <password>")
            sender.send_message("§cUsage: /eco import sqlite <file_path>")
            return
        
        db_type = args[0].lower()
        if db_type == "mysql":
            if len(args) < 6:
                sender.send_message("§cUsage: /eco import mysql <host> <port> <database> <username> <password>")
                return
            try:
                host = args[1]
                port = int(args[2])
                db_name = args[3]
                user = args[4]
                password = args[5]
                self._handle_import_mysql(sender, host, port, db_name, user, password)
            except ValueError:
                sender.send_message("§cError: Port must be an integer.")
        elif db_type == "sqlite":
            if len(args) < 2:
                sender.send_message("§cUsage: /eco import sqlite <file_path>")
                return
            file_path = args[1]
            self._handle_import_sqlite(sender, file_path)
        else:
            sender.send_message("§cUsage: /eco import mysql <host> <port> <database> <username> <password>")
            sender.send_message("§cUsage: /eco import sqlite <file_path>")

    def _handle_import_mysql(self, sender: CommandSender, host: str, port: int, db_name: str, user: str, password: str) -> None:
        async def task():
            try:
                self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message("§eStarting MySQL import..."))
                
                try:
                    import aiomysql
                except ImportError:
                    self._plugin.server.scheduler.run_task(
                        self._plugin, 
                        lambda: sender.send_message("§cError: aiomysql is not installed on the system.")
                    )
                    return

                conn = await aiomysql.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    db=db_name,
                    autocommit=True
                )
                
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute("SHOW TABLES")
                    tables = [list(r.values())[0] for r in await cursor.fetchall()]
                    
                    has_players = "players" in tables
                    has_profiles = "player_profiles" in tables
                    
                    if not has_players and not has_profiles:
                        self._plugin.server.scheduler.run_task(
                            self._plugin, 
                            lambda: sender.send_message("§cError: No 'players' or 'player_profiles' table found in the source database.")
                        )
                        conn.close()
                        return
                    
                    profiles_table = "players" if has_players else "player_profiles"
                    self._plugin.server.scheduler.run_task(
                        self._plugin, 
                        lambda: sender.send_message(f"§eFound table '{profiles_table}'. Fetching player profiles...")
                    )
                    
                    await cursor.execute(f"SELECT uuid, username FROM {profiles_table}")
                    source_profiles = await cursor.fetchall()
                    
                    self._plugin.server.scheduler.run_task(
                        self._plugin, 
                        lambda: sender.send_message("§eFetching player balances...")
                    )
                    await cursor.execute("SELECT uuid, currency, balance FROM balances")
                    source_balances = await cursor.fetchall()
                
                conn.close()
                
                profile_entries = []
                for p in source_profiles:
                    uuid = p["uuid"]
                    username = p["username"]
                    profile_entries.append((uuid, None, username))
                    
                balance_entries = []
                for b in source_balances:
                    uuid = b["uuid"]
                    currency = b["currency"]
                    balance = float(b["balance"])
                    balance_entries.append((uuid, currency, balance))
                    
                self._plugin.server.scheduler.run_task(
                    self._plugin, 
                    lambda: sender.send_message(f"§eUpserting {len(profile_entries)} player profiles in active DB...")
                )
                await self._plugin._profile_repo.batch_upsert_profiles(profile_entries)
                
                self._plugin.server.scheduler.run_task(
                    self._plugin, 
                    lambda: sender.send_message(f"§eUpserting {len(balance_entries)} balances in active DB...")
                )
                await self._plugin._balance_repo.batch_set_balances(balance_entries)
                
                self._plugin._balance_cache.invalidate_all()
                
                self._plugin.server.scheduler.run_task(
                    self._plugin, 
                    lambda: sender.send_message(f"§aImport successful! Imported {len(profile_entries)} profiles and {len(balance_entries)} balances.")
                )
                
            except Exception as e:
                self._plugin.logger.error(f"Error importing from MySQL: {e}")
                self._plugin.server.scheduler.run_task(
                    self._plugin, 
                    lambda: sender.send_message(f"§cError during import: {e}")
                )
        self._plugin.run_async(task())

    def _handle_import_sqlite(self, sender: CommandSender, file_path: str) -> None:
        async def task():
            try:
                self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message("§eStarting SQLite import..."))
                
                if not os.path.exists(file_path):
                    self._plugin.server.scheduler.run_task(
                        self._plugin, 
                        lambda: sender.send_message(f"§cError: SQLite file not found at '{file_path}'.")
                    )
                    return
                
                import aiosqlite
                conn = await aiosqlite.connect(file_path)
                conn.row_factory = aiosqlite.Row
                
                cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r["name"] for r in await cursor.fetchall()]
                
                has_players = "players" in tables
                has_profiles = "player_profiles" in tables
                
                if not has_players and not has_profiles:
                    self._plugin.server.scheduler.run_task(
                        self._plugin, 
                        lambda: sender.send_message("§cError: No 'players' or 'player_profiles' table found in the source SQLite file.")
                    )
                    await conn.close()
                    return
                
                profiles_table = "players" if has_players else "player_profiles"
                self._plugin.server.scheduler.run_task(
                    self._plugin, 
                    lambda: sender.send_message(f"§eFound table '{profiles_table}'. Fetching player profiles...")
                )
                
                cursor = await conn.execute(f"SELECT uuid, username FROM {profiles_table}")
                source_profiles = await cursor.fetchall()
                
                self._plugin.server.scheduler.run_task(
                    self._plugin, 
                    lambda: sender.send_message("§eFetching player balances...")
                )
                cursor = await conn.execute("SELECT uuid, currency, balance FROM balances")
                source_balances = await cursor.fetchall()
                
                await conn.close()
                
                profile_entries = []
                for p in source_profiles:
                    uuid = p["uuid"]
                    username = p["username"]
                    profile_entries.append((uuid, None, username))
                    
                balance_entries = []
                for b in source_balances:
                    uuid = b["uuid"]
                    currency = b["currency"]
                    balance = float(b["balance"])
                    balance_entries.append((uuid, currency, balance))
                    
                self._plugin.server.scheduler.run_task(
                    self._plugin, 
                    lambda: sender.send_message(f"§eUpserting {len(profile_entries)} player profiles in active DB...")
                )
                await self._plugin._profile_repo.batch_upsert_profiles(profile_entries)
                
                self._plugin.server.scheduler.run_task(
                    self._plugin, 
                    lambda: sender.send_message(f"§eUpserting {len(balance_entries)} balances in active DB...")
                )
                await self._plugin._balance_repo.batch_set_balances(balance_entries)
                
                self._plugin._balance_cache.invalidate_all()
                
                self._plugin.server.scheduler.run_task(
                    self._plugin, 
                    lambda: sender.send_message(f"§aImport successful! Imported {len(profile_entries)} profiles and {len(balance_entries)} balances.")
                )
                
            except Exception as e:
                self._plugin.logger.error(f"Error importing from SQLite: {e}")
                self._plugin.server.scheduler.run_task(
                    self._plugin, 
                    lambda: sender.send_message(f"§cError during import: {e}")
                )
        self._plugin.run_async(task())

    def _parse_amount(self, sender: CommandSender, value: str) -> float | None:
        try:
            amount = float(value)
        except ValueError:
            sender.send_message(self._plugin.message_formatter.format("pay_invalid_amount"))
            return None
        if amount <= 0:
            sender.send_message(self._plugin.message_formatter.format("pay_invalid_amount"))
            return None
        return amount

    def _show_usage(self, sender: CommandSender) -> None:
        sender.send_message("§6§l--- JWEconomy Admin ---§r")
        sender.send_message("§e/eco give <player> <amount> [currency] §7- Give money")
        sender.send_message("§e/eco take <player> <amount> [currency] §7- Take money")
        sender.send_message("§e/eco set <player> <amount> [currency] §7- Set balance")
        sender.send_message("§e/eco top [page] [currency] §7- Balance leaderboard")
        sender.send_message("§e/eco reload §7- Reload config")
        sender.send_message("§e/eco import mysql <host> <port> <database> <username> <password> §7- Import from MySQL")
        sender.send_message("§e/eco import sqlite <file_path> §7- Import from SQLite")
