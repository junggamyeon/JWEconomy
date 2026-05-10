

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
        if len(args) == 0:
            if not isinstance(sender, Player):
                sender.send_message(self._plugin.message_formatter.format("player_only"))
                return True
            self._show_self_balance(sender)
        elif len(args) == 1:
            self._show_other_balance(sender, args[0])
        else:
            sender.send_message(self._plugin.message_formatter.format("usage_error", usage="/balance [player]"))
        return True

    def _show_self_balance(self, player: Player) -> None:
        uuid = str(player.unique_id)
        async def task():
            try:
                balance = await self._plugin.economy_service.get_balance(uuid)
                def callback():
                    symbol = self._plugin.economy_service.currency_symbol
                    formatted = self._plugin.message_formatter.format_amount(balance, symbol)
                    player.send_message(self._plugin.message_formatter.format("balance_self", symbol=symbol, amount=formatted))
                self._plugin.server.scheduler.run_task(self._plugin, callback)
            except Exception as e:
                self._plugin.logger.error(f"Error getting self balance: {e}")
                self._plugin.server.scheduler.run_task(self._plugin, lambda: player.send_message(self._plugin.message_formatter.format("error_generic")))
        self._plugin.run_async(task())

    def _show_other_balance(self, sender: CommandSender, target_name: str) -> None:
        async def task():
            try:
                service = self._plugin.economy_service
                target_uuid = await service.get_uuid_by_name(target_name)
                if target_uuid is None:
                    self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message(self._plugin.message_formatter.format("balance_not_found")))
                    return
                balance = await service.get_balance(target_uuid)
                def callback():
                    symbol = service.currency_symbol
                    formatted = self._plugin.message_formatter.format_amount(balance, symbol)
                    sender.send_message(self._plugin.message_formatter.format("balance_other", player=target_name, symbol=symbol, amount=formatted))
                self._plugin.server.scheduler.run_task(self._plugin, callback)
            except Exception as e:
                self._plugin.logger.error(f"Error getting other balance: {e}")
                self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message(self._plugin.message_formatter.format("error_generic")))
        self._plugin.run_async(task())
