from typing import Optional
from endstone import Player
import asyncio

try:
    from jwplaceholderapi.expansion import PlaceholderExpansion
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

        # Hỗ trợ format: balance_[currency], balance_raw_[currency]
        # Nếu chỉ có "balance" hoặc "balance_raw" sẽ dùng currency mặc định (None)
        currency = None
        is_raw = False

        if params.startswith("balance_raw_"):
            is_raw = True
            currency = params[len("balance_raw_"):]
        elif params == "balance_raw":
            is_raw = True
        elif params.startswith("balance_short_"):
            currency = params[len("balance_short_"):]
        elif params.startswith("balance_"):
            currency = params[len("balance_"):]
        elif params in ["balance", "balance_short"]:
            pass
        else:
            return None # Không khớp mẫu

        try:
            uuid_str = str(player.unique_id)
            
            # JWEconomy get_balance is async
            api = self.plugin.get_api()
            coro = api.get_balance(uuid_str, currency)
            future = self.plugin.run_async(coro)
            balance = future.result(timeout=2.0)
            
            if is_raw:
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
