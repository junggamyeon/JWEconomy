from typing import Optional
from endstone import Player
import asyncio

try:
    from placeholder_api.expansion import PlaceholderExpansion
except ImportError:
    PlaceholderExpansion = object # Fallback if not installed

class JWEconomyExpansion(PlaceholderExpansion):
    def __init__(self, plugin):
        self.plugin = plugin
        super().__init__()

    def get_identifier(self) -> str:
        return "jweco"

    def get_author(self) -> str:
        return "JWDev"

    def get_version(self) -> str:
        return "1.0.0"

    def on_request(self, player: Optional[Player], params: str) -> Optional[str]:
        if not player:
            return None

        if params in ["balance", "balance_raw", "balance_short"]:
            try:
                uuid_str = str(player.unique_id)
                
                # JWEconomy get_balance is async
                api = self.plugin.get_api()
                coro = api.get_balance(uuid_str, None)
                future = self.plugin.run_async(coro)
                balance = future.result(timeout=2.0)
                
                if params == "balance_raw":
                    return f"{balance:.2f}"
                else:
                    if balance >= 1000000000:
                        return f"{balance / 1000000000.0:.1f}B"
                    elif balance >= 1000000:
                        return f"{balance / 1000000.0:.1f}M"
                    elif balance >= 1000:
                        return f"{balance / 1000.0:.1f}k"
                    else:
                        return f"{balance:.2f}"
            except Exception:
                return "0"
                
        return None
