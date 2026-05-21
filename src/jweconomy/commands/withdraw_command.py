from __future__ import annotations

from typing import TYPE_CHECKING
from endstone import Player
from endstone.command import CommandSender
from endstone.inventory import ItemStack

if TYPE_CHECKING:
    from jweconomy.main import JWEconomy

class WithdrawCommandHandler:
    def __init__(self, plugin: JWEconomy) -> None:
        self._plugin = plugin

    def handle(self, sender: CommandSender, args: list[str]) -> bool:
        if not isinstance(sender, Player):
            sender.send_message(self._plugin.message_formatter.format("player_only"))
            return True

        if len(args) < 1:
            sender.send_message(self._plugin.message_formatter.format("usage_error", usage="/withdraw <amount> [currency]"))
            return True

        amount = self._parse_amount(sender, args[0])
        if amount is None:
            return True

        service = self._plugin.economy_service
        currency = service.default_currency
        if len(args) >= 2:
            currency_arg = args[1]
            matched_currency = None
            for c in service.currencies:
                if c.lower() == currency_arg.lower():
                    matched_currency = c
                    break
            if matched_currency is None:
                sender.send_message(f"§cInvalid currency. Available: {', '.join(service.currencies)}")
                return True
            currency = matched_currency

        currency_config = service._get_currency_config(currency)
        if not currency_config.get("is_withdrawable", True):
            sender.send_message(self._plugin.message_formatter.format("withdraw_disabled"))
            return True

        min_withdraw = self._plugin._config_loader.economy_config.get("min_withdraw", 1.0)
        max_withdraw = self._plugin._config_loader.economy_config.get("max_withdraw", 1000000.0)

        if amount < min_withdraw or amount > max_withdraw:
            sender.send_message(self._plugin.message_formatter.format("withdraw_limit", min=min_withdraw, max=max_withdraw))
            return True

        async def task():
            try:
                symbol = service.get_currency_symbol(currency)
                has_enough = await service.has_balance(sender.unique_id, amount, currency)
                if not has_enough:
                    self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message(self._plugin.message_formatter.format("pay_insufficient")))
                    return

                await service.remove_balance(sender.unique_id, amount, currency)

                def callback():
                    material = currency_config.get("withdraw_material", "minecraft:paper")
                    item = ItemStack(material)
                    meta = item.item_meta
                    
                    display_name = currency_config.get("withdraw_name", "§bBank Note")
                    display_name = display_name.replace("%amount%", f"{symbol}{amount}").replace("%currency%", currency).replace("%player%", sender.name)
                    meta.display_name = display_name

                    lore = currency_config.get("withdraw_lore", ["§7Signer: §f%player%", "§7Value: §f%amount%"])
                    formatted_lore = [line.replace("%amount%", f"{symbol}{amount}").replace("%currency%", currency).replace("%player%", sender.name) for line in lore]
                    
                    # Hidden line to parse data reliably
                    formatted_lore.append(f"§0JWE_WD|{currency}|{amount}|{sender.name}")
                    meta.lore = formatted_lore
                    item.item_meta = meta

                    sender.inventory.add_item(item)
                    sender.send_message(self._plugin.message_formatter.format("withdraw_success", amount=f"{symbol}{amount}", currency=currency))

                self._plugin.server.scheduler.run_task(self._plugin, callback)
            except Exception as e:
                self._plugin.logger.error(f"Error in withdraw: {e}")
                self._plugin.server.scheduler.run_task(self._plugin, lambda: sender.send_message(self._plugin.message_formatter.format("error_generic")))

        self._plugin.run_async(task())
        return True

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