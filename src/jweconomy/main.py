

from __future__ import annotations

import asyncio
import os
import threading
from typing import TYPE_CHECKING, Any

from endstone.plugin import Plugin
from endstone.command import Command, CommandSender

from jweconomy.api.economy_api import EconomyAPI
from jweconomy.cache.balance_cache import BalanceCache
from jweconomy.commands.balance_command import BalanceCommandHandler
from jweconomy.commands.eco_command import EcoCommandHandler
from jweconomy.commands.pay_command import PayCommandHandler
from jweconomy.commands.withdraw_command import WithdrawCommandHandler
from jweconomy.database.database_manager import DatabaseManager
from jweconomy.database.repositories.balance_repository import BalanceRepository
from jweconomy.database.repositories.profile_repository import ProfileRepository
from jweconomy.database.repositories.transaction_repository import TransactionRepository
from jweconomy.database.schema import SchemaManager
from jweconomy.listeners.player_listener import PlayerListener
from jweconomy.services.economy_service import EconomyService
from jweconomy.util.config_loader import ConfigLoader
from jweconomy.util.message_formatter import MessageFormatter

if TYPE_CHECKING:
    from concurrent.futures import Future


class JWEconomy(Plugin):


    api_version = "0.11"
    prefix = "§6§l[JWEconomy]§r"
    version = "2.0.0"
    description = "Modern economy system with SQLite backend, caching, and async operations."
    authors = ["JWDev"]
    soft_depend = ["jwplaceholderapi"]

    commands = {
        "balance": {
            "description": "Check your balance or another player's balance",
            "usages": [
                "/balance",
                "/balance <player: string>",
                "/balance <player: string> <currency: string>"
            ],
            "aliases": ["bal", "money"],
        },
        "pay": {
            "description": "Pay another player",
            "usages": [
                "/pay <player: string> <amount: float>",
                "/pay <player: string> <amount: float> <currency: string>"
            ],
        },
        "eco": {
            "description": "Economy admin commands",
            "usages": [
                "/eco give <player: string> <amount: float>",
                "/eco give <player: string> <amount: float> <currency: string>",
                "/eco take <player: string> <amount: float>",
                "/eco take <player: string> <amount: float> <currency: string>",
                "/eco set <player: string> <amount: float>",
                "/eco set <player: string> <amount: float> <currency: string>",
                "/eco top",
                "/eco top <page: int>",
                "/eco top <currency: string>",
                "/eco top <page: int> <currency: string>",
                "/eco reload",
                "/eco import mysql <host: string> <port: int> <database: string> <username: string> <password: string>",
                "/eco import sqlite <file_path: string>",
            ],
            "permissions": ["jweconomy.admin"],
        },
        "withdraw": {
            "description": "Withdraw money into a physical bank note",
            "usages": [
                "/withdraw <amount: float>",
                "/withdraw <amount: float> <currency: string>"
            ],
        },
    }

    permissions = {
        "jweconomy.admin": {
            "description": "Allows use of economy admin commands",
            "default": "op",
        },
    }

    _instance: JWEconomy | None = None

    @classmethod
    def get_instance(cls) -> JWEconomy:
        if cls._instance is None:
            raise RuntimeError("JWEconomy is not loaded")
        return cls._instance

    def on_load(self) -> None:
        JWEconomy._instance = self
        self._async_loop: asyncio.AbstractEventLoop | None = None
        self._async_thread: threading.Thread | None = None

        self._config_loader = ConfigLoader(self.data_folder, self.logger)
        self._config_loader.load_all()
        self._message_formatter = MessageFormatter(self._config_loader.messages)

        self._db_manager = DatabaseManager(self._config_loader.database_config, str(self.data_folder), self.logger)
        
        self._balance_cache = BalanceCache(
            max_size=self._config_loader.economy_config.get("cache_max_size", 500),
            ttl_seconds=self._config_loader.economy_config.get("cache_ttl_seconds", 300),
        )

        self._start_async_loop()

    def on_enable(self) -> None:
        future = self.run_async(self._initialize_database())
        try:
            future.result(timeout=10.0)
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            self.server.plugin_manager.disable_plugin(self)
            return

        self._balance_repo = BalanceRepository(self._db_manager)
        self._profile_repo = ProfileRepository(self._db_manager)
        self._transaction_repo = TransactionRepository(self._db_manager)

        self._economy_service = EconomyService(
            balance_repo=self._balance_repo,
            transaction_repo=self._transaction_repo,
            profile_repo=self._profile_repo,
            cache=self._balance_cache,
            config=self._config_loader.economy_config,
            logger=self.logger,
        )
        self._economy_api = EconomyAPI(self._economy_service, self._balance_cache)

        self._cmd_balance = BalanceCommandHandler(self)
        self._cmd_pay = PayCommandHandler(self)
        self._cmd_eco = EcoCommandHandler(self)
        self._cmd_withdraw = WithdrawCommandHandler(self)

        self.register_events(PlayerListener(self))

        # Register JWPlaceholderAPI expansion
        papi = self.server.plugin_manager.get_plugin("jwplaceholderapi")
        if papi:
            from jweconomy.jweconomy_expansion import JWEconomyExpansion
            try:
                papi.register_expansion(JWEconomyExpansion(self))
            except Exception as e:
                self.logger.warning(f"Failed to register PlaceholderAPI expansion: {e}")

        # Schedule cache flush task (every 60 seconds)
        self.server.scheduler.run_task(self, self._flush_cache_task, delay=1200, period=1200)

    def on_disable(self) -> None:
        if hasattr(self, "_economy_service"):
            try:
                # Flush cache on disable
                future = self.run_async(self._balance_cache.flush_all(self._economy_service))
                future.result(timeout=5.0)
            except Exception as e:
                self.logger.error(f"Error flushing cache on disable: {e}")

        future = self.run_async(self._db_manager.close())
        try:
            future.result(timeout=5.0)
        except Exception as e:
            self.logger.error(f"Error closing database: {e}")

        self._stop_async_loop()

    def on_command(self, sender: CommandSender, command: Command, args: list[str]) -> bool:
        cmd_name = command.name.lower()
        if cmd_name == "balance":
            return self._cmd_balance.handle(sender, args)
        elif cmd_name == "pay":
            return self._cmd_pay.handle(sender, args)
        elif cmd_name == "eco":
            return self._cmd_eco.handle(sender, args)
        elif cmd_name == "withdraw":
            return self._cmd_withdraw.handle(sender, args)
        return False

    def run_async(self, coro: Any) -> Future:
        if self._async_loop is None or not self._async_loop.is_running():
            raise RuntimeError("Async loop is not running")
        return asyncio.run_coroutine_threadsafe(coro, self._async_loop)

    def _start_async_loop(self) -> None:
        def loop_runner():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._async_loop = loop
            loop.run_forever()
            loop.close()

        self._async_thread = threading.Thread(target=loop_runner, name="JWEconomyAsyncThread", daemon=True)
        self._async_thread.start()

    def _stop_async_loop(self) -> None:
        if self._async_loop and self._async_loop.is_running():
            self._async_loop.call_soon_threadsafe(self._async_loop.stop)
        if self._async_thread:
            self._async_thread.join(timeout=5.0)

    async def _initialize_database(self) -> None:
        await self._db_manager.connect()
        schema_manager = SchemaManager(self._db_manager, self.logger)
        await schema_manager.create_tables(self._config_loader.economy_config.get("default_currency", "coins"))

    def _flush_cache_task(self) -> None:
        if hasattr(self, "_economy_service"):
            self.run_async(self._balance_cache.flush_all(self._economy_service))

    @property
    def message_formatter(self) -> MessageFormatter:
        return self._message_formatter

    @property
    def economy_service(self) -> EconomyService:
        return self._economy_service

    def get_api(self) -> EconomyAPI:
        return self._economy_api

    @property
    def economy_api(self) -> EconomyAPI:
        return self._economy_api

    @property
    def balance_cache(self) -> BalanceCache:
        return self._balance_cache
