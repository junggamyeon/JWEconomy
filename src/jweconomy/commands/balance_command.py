

from __future__ import annotations

from typing import TYPE_CHECKING

from endstone import Player
from endstone.command import CommandSender

if TYPE_CHECKING:
    from jweconomy.main import JWEconomy


class BalanceCommandHandler:
    def __init__(self, plugin: JWEconomy) -> None:
        self._plugin = plugin

    def handle(self, sender: CommandSender, args: list[str]) -> bool:
        service = self._plugin.economy_service
        currencies = service.currencies

        if len(args) == 0:
            if not isinstance(sender, Player):
                sender.send_message(self._plugin.message_formatter.format("player_only"))
                return True
            self._show_self_balance(sender, service.default_currency)
        elif len(args) == 1:
            arg = args[0]
            matched_currency = None
            for c in currencies:
                if c.lower() == arg.lower():
                    matched_currency = c
                    break

            if matched_currency is not None:
                if not isinstance(sender, Player):
                    sender.send_message(self._plugin.message_formatter.format("player_only"))
                    return True
                self._show_self_balance(sender, matched_currency)
            else:
                self._show_other_balance(sender, arg, service.default_currency)
        else:
            target_name = args[0]
            currency_arg = args[1]
            matched_currency = None
            for c in currencies:
                if c.lower() == currency_arg.lower():
                    matched_currency = c
                    break

            if matched_currency is None:
                sender.send_message(f"§cInvalid currency. Available: {', '.join(currencies)}")
                return True
            self._show_other_balance(sender, target_name, matched_currency)
        return True

    def _show_self_balance(self, player: Player, currency: str) -> None:
        uuid = str(player.unique_id)
        async def task():
            try:
                service = self._plugin.economy_service
                balance = await service.get_balance(uuid, currency)
                def callback():
                    symbol = service.get_currency_symbol(currency)
                    formatted = self._plugin.message_formatter.format_amount(balance, symbol)
                    player.send_message(self._plugin.message_formatter.format("balance_self", symbol=symbol, amount=formatted))
                self._plugin.server.scheduler.run_task(self._plugin, callback)
            except Exception as e:
                self._plugin.logger.error(f"Error getting self balance: {e}")
                self._plugin.server.scheduler.run_task(self._plugin, lambda: player.send_message(self._plugin.message_formatter.format("error_generic")))
        self._plugin.run_async(task())

    def _show_other_balance(self, sender: CommandSender, target_name: str, currency: str) -> None:
        async def task():
            try:
                service = self._plugin.economy_service
                target_uuid = await service.get_uuid_by_name(target_name)
                if target_uuid is None:
                    self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message(self._plugin.message_formatter.format("balance_not_found")))
                    return
                balance = await service.get_balance(target_uuid, currency)
                def callback():
                    symbol = service.get_currency_symbol(currency)
                    formatted = self._plugin.message_formatter.format_amount(balance, symbol)
                    sender.send_message(self._plugin.message_formatter.format("balance_other", player=target_name, symbol=symbol, amount=formatted))
                self._plugin.server.scheduler.run_task(self._plugin, callback)
            except Exception as e:
                self._plugin.logger.error(f"Error getting other balance: {e}")
                self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message(self._plugin.message_formatter.format("error_generic")))
        self._plugin.run_async(task())

