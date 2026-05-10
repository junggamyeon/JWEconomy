

from __future__ import annotations

from typing import Any


class MessageFormatter:


    def __init__(self, messages: dict[str, str]) -> None:
        self._messages = messages
        self._prefix = messages.get("prefix", "§6§l[JWEconomy]§r ")

    def format(self, key: str, **kwargs: Any) -> str:
        template = self._messages.get(key, f"§cMissing message: {key}")
        kwargs.setdefault("prefix", self._prefix)
        try:
            return template.format(**kwargs)
        except KeyError as e:
            return f"§cMessage format error for '{key}': missing {e}"

    def format_amount(self, amount: float, symbol: str = "$") -> str:
        if amount == int(amount):
            return f"{symbol}{int(amount):,}"
        return f"{symbol}{amount:,.2f}"

    def reload(self, messages: dict[str, str]) -> None:
        self._messages = messages
        self._prefix = messages.get("prefix", "§6§l[JWEconomy]§r ")
