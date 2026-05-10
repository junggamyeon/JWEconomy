

from __future__ import annotations

from typing import TYPE_CHECKING

from endstone import Player
from endstone.command import CommandSender

if TYPE_CHECKING:
    from jweconomy.main import JWEconomy


class PayCommandHandler:
    def __init__(self, plugin: JWEconomy) -> None:
        self._plugin = plugin

    def handle(self, sender: CommandSender, args: list[str]) -> bool:
        if not isinstance(sender, Player):
            sender.send_message(self._plugin.message_formatter.format("player_only"))
            return True
        if len(args) < 2:
            sender.send_message(self._plugin.message_formatter.format("usage_error", usage="/pay <player> <amount>"))
            return True
        target_name = args[0]
        try:
            amount = float(args[1])
        except ValueError:
            sender.send_message(self._plugin.message_formatter.format("pay_invalid_amount"))
            return True
        if amount <= 0:
            sender.send_message(self._plugin.message_formatter.format("pay_invalid_amount"))
            return True
        self._process_payment(sender, target_name, amount)
        return True

    def _process_payment(self, sender: Player, target_name: str, amount: float) -> None:
        service = self._plugin.economy_service
        symbol = service.currency_symbol
        sender_uuid = str(sender.unique_id)

        async def task():
            try:
                target_uuid = await service.get_uuid_by_name(target_name)
                if target_uuid is None:
                    self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message(self._plugin.message_formatter.format("pay_player_offline")))
                    return
                if target_uuid == sender_uuid:
                    self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message(self._plugin.message_formatter.format("pay_self")))
                    return

                result = await service.transfer_balance(sender_uuid, target_uuid, amount)
                def callback():
                    if not result.success:
                        sender.send_message(self._plugin.message_formatter.format("pay_insufficient"))
                        return

                    formatted = self._plugin.message_formatter.format_amount(amount, symbol)
                    sender.send_message(self._plugin.message_formatter.format("pay_success", symbol=symbol, amount=formatted, target=target_name))

                    if result.tax_amount > 0:
                        tax_formatted = self._plugin.message_formatter.format_amount(result.tax_amount, symbol)
                        sender.send_message(self._plugin.message_formatter.format("pay_tax_notice", symbol=symbol, tax_amount=tax_formatted, tax_percent=service.transfer_tax_percent))

                    target_player = self._plugin.server.get_player(target_name)
                    if target_player:
                        target_player.send_message(self._plugin.message_formatter.format("pay_received", symbol=symbol, amount=formatted, sender=sender.name))
                self._plugin.server.scheduler.run_task(self._plugin, callback)
            except Exception as e:
                self._plugin.logger.error(f"Error processing payment: {e}")
                self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message(self._plugin.message_formatter.format("error_generic")))
        self._plugin.run_async(task())
