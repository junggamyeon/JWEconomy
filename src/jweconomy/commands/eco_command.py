

from __future__ import annotations

from typing import TYPE_CHECKING

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
        else:
            self._show_usage(sender)
        return True

    def _handle_give(self, sender: CommandSender, args: list[str]) -> None:
        if len(args) < 2:
            sender.send_message(self._plugin.message_formatter.format("usage_error", usage="/eco give <player> <amount>"))
            return
        target_name, amount = args[0], self._parse_amount(sender, args[1])
        if amount is None:
            return
        async def task():
            try:
                service = self._plugin.economy_service
                symbol = service.currency_symbol
                target_uuid = await service.get_uuid_by_name(target_name)
                if target_uuid is None:
                    self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message(self._plugin.message_formatter.format("balance_not_found")))
                    return
                await service.add_balance(target_uuid, amount)
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
            sender.send_message(self._plugin.message_formatter.format("usage_error", usage="/eco take <player> <amount>"))
            return
        target_name, amount = args[0], self._parse_amount(sender, args[1])
        if amount is None:
            return
        async def task():
            try:
                service = self._plugin.economy_service
                symbol = service.currency_symbol
                target_uuid = await service.get_uuid_by_name(target_name)
                if target_uuid is None:
                    self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message(self._plugin.message_formatter.format("balance_not_found")))
                    return
                result = await service.remove_balance(target_uuid, amount)
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
            sender.send_message(self._plugin.message_formatter.format("usage_error", usage="/eco set <player> <amount>"))
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
        async def task():
            try:
                service = self._plugin.economy_service
                symbol = service.currency_symbol
                target_uuid = await service.get_uuid_by_name(target_name)
                if target_uuid is None:
                    self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message(self._plugin.message_formatter.format("balance_not_found")))
                    return
                new_balance = await service.set_balance(target_uuid, amount)
                def callback():
                    formatted = self._plugin.message_formatter.format_amount(new_balance, symbol)
                    sender.send_message(self._plugin.message_formatter.format("eco_set", symbol=symbol, amount=formatted, player=target_name))
                self._plugin.server.scheduler.run_task(self._plugin, callback)
            except Exception as e:
                self._plugin.logger.error(f"Error in eco set: {e}")
                self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message(self._plugin.message_formatter.format("error_generic")))
        self._plugin.run_async(task())

    def _handle_top(self, sender: CommandSender, args: list[str]) -> None:
        page = 1
        if len(args) >= 1:
            try:
                page = max(1, int(args[0]))
            except ValueError:
                page = 1
        async def task():
            try:
                service = self._plugin.economy_service
                symbol = service.currency_symbol
                per_page = self._plugin._config_loader.economy_config.get("top_entries_per_page", 10)
                offset = (page - 1) * per_page
                entries = await service.get_top_balances(per_page, offset)
                def callback():
                    if not entries:
                        sender.send_message(self._plugin.message_formatter.format("eco_top_empty"))
                        return
                    sender.send_message(self._plugin.message_formatter.format("eco_top_header"))
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
        sender.send_message("§e/eco give <player> <amount> §7- Give money")
        sender.send_message("§e/eco take <player> <amount> §7- Take money")
        sender.send_message("§e/eco set <player> <amount> §7- Set balance")
        sender.send_message("§e/eco top [page] §7- Balance leaderboard")
        sender.send_message("§e/eco reload §7- Reload config")
