

from typing import TYPE_CHECKING

from endstone.event import PlayerJoinEvent, PlayerQuitEvent, PlayerInteractEvent, event_handler

if TYPE_CHECKING:
    from jweconomy.main import JWEconomy


class PlayerListener:
    def __init__(self, plugin: 'JWEconomy') -> None:
        self._plugin = plugin

    @event_handler
    def on_player_join(self, event: PlayerJoinEvent) -> None:
        player = event.player
        uuid = str(player.unique_id)
        xuid = player.xuid
        username = player.name
        try:
            self._plugin.run_async(self._plugin.economy_service.initialize_player(uuid, xuid, username))
        except Exception as e:
            self._plugin.logger.error(f"Error initializing player {username}: {e}")

    @event_handler
    def on_player_quit(self, event: PlayerQuitEvent) -> None:
        player = event.player
        uuid = str(player.unique_id)
        cache = self._plugin.balance_cache
        dirty = cache.get_dirty_entries()
        player_dirty = []
        other_dirty = []
        for u, c, b in dirty:
            if u == uuid:
                player_dirty.append((u, c, b))
            else:
                other_dirty.append((u, c, b))

        if player_dirty:
            try:
                self._plugin.run_async(self._plugin.economy_service.batch_save_balances(player_dirty))
            except Exception as e:
                self._plugin.logger.error(f"Error saving balance on quit for {player.name}: {e}")

        for u, c, b in other_dirty:
            cache.set(u, c, b, dirty=True)

        cache.invalidate(uuid)

    @event_handler
    def on_player_interact(self, event: PlayerInteractEvent) -> None:
        player = event.player
        item = event.item
        if not item:
            return

        meta = item.item_meta
        if not meta or not meta.lore:
            return

        hidden_line = None
        for line in meta.lore:
            if line.startswith("§0JWE_WD|"):
                hidden_line = line
                break
        
        if hidden_line is None:
            return

        parts = hidden_line.split("|")
        if len(parts) != 4:
            return

        currency = parts[1]
        try:
            amount = float(parts[2])
        except ValueError:
            return
            
        # Cancel the event to prevent block placement or other interactions
        event.is_cancelled = True

        service = self._plugin.economy_service
        symbol = service.get_currency_symbol(currency)

        async def task():
            try:
                await service.add_balance(str(player.unique_id), amount, currency)
                def callback():
                    # Deduct the item
                    if item.amount > 1:
                        item.amount -= 1
                        player.inventory.set_item(player.inventory.item_in_hand_index, item)
                    else:
                        from endstone.inventory import ItemStack
                        player.inventory.set_item(player.inventory.item_in_hand_index, ItemStack("minecraft:air"))
                    
                    player.send_message(self._plugin.message_formatter.format("withdraw_redeem", amount=f"{symbol}{amount}", currency=currency))
                self._plugin.server.scheduler.run_task(self._plugin, callback)
            except Exception as e:
                self._plugin.logger.error(f"Error redeeming withdraw item: {e}")
                self._plugin.server.scheduler.run_task(self._plugin, lambda: player.send_message(self._plugin.message_formatter.format("error_generic")))

        self._plugin.run_async(task())
