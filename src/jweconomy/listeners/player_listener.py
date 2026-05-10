

from typing import TYPE_CHECKING

from endstone.event import PlayerJoinEvent, PlayerQuitEvent, event_handler

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
        player_dirty = [(u, b) for u, b in dirty if u == uuid]
        if player_dirty:
            try:
                self._plugin.run_async(self._plugin.economy_service.batch_save_balances(player_dirty))
            except Exception as e:
                self._plugin.logger.error(f"Error saving balance on quit for {player.name}: {e}")
        cache.invalidate(uuid)
