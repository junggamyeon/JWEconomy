

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from endstone import Logger

_DEFAULT_CONFIG = {
    "database": {
        "type": "sqlite",  # sqlite or mysql
        "filename": "jweconomy.db",
        "mysql": {
            "host": "localhost",
            "port": 3306,
            "database": "jweconomy",
            "username": "root",
            "password": "",
            "pool_min_size": 1,
            "pool_max_size": 10,
        },
    },
    "economy": {
        "default_currency": "coins",
        "currencies": {
            "coins": {
                "starting_balance": 1000.0,
                "currency_symbol": "$",
                "currency_name": "Coins",
                "currency_name_plural": "Coins",
                "max_balance": 1_000_000_000.0,
                "is_withdrawable": True,
                "withdraw_material": "minecraft:paper",
                "withdraw_name": "§aBank Note",
                "withdraw_lore": [
                    "§7Signer: §f%player%",
                    "§7Value: §e%amount%",
                    "",
                    "§eRight-click to redeem"
                ]
            },
            "gems": {
                "starting_balance": 10.0,
                "currency_symbol": "💎",
                "currency_name": "Gem",
                "currency_name_plural": "Gems",
                "max_balance": 1_000_000.0,
                "is_withdrawable": True,
                "withdraw_material": "minecraft:emerald",
                "withdraw_name": "§bGem Voucher",
                "withdraw_lore": [
                    "§7Signer: §f%player%",
                    "§7Value: §b%amount%",
                    "",
                    "§bRight-click to redeem"
                ]
            },
        },
        "min_transaction": 0.01,
        "min_withdraw": 1.0,
        "max_withdraw": 1000000.0,
        "transfer_tax_percent": 0.0,
        "top_entries_per_page": 10,
        "cache_max_size": 500,
        "cache_ttl_seconds": 300,
    },
}

_DEFAULT_MESSAGES = {
    "prefix": "[JWEconomy] ",
    "balance_self": "{prefix}Your balance: {amount}",
    "balance_other": "{prefix}{player}'s balance: {amount}",
    "balance_not_found": "{prefix}Player not found.",
    "pay_success": "{prefix}You paid {amount} to {target}.",
    "pay_received": "{prefix}You received {amount} from {sender}.",
    "pay_tax_notice": "{prefix}Tax applied: {tax_amount} ({tax_percent}%)",
    "pay_insufficient": "{prefix}Insufficient balance.",
    "pay_self": "{prefix}You cannot pay yourself.",
    "pay_invalid_amount": "{prefix}Invalid amount. Must be a positive number.",
    "pay_player_offline": "{prefix}Player not found or offline.",
    "eco_give": "{prefix}Gave {amount} to {player}.",
    "eco_take": "{prefix}Took {amount} from {player}.",
    "eco_set": "{prefix}Set {player}'s balance to {amount}.",
    "eco_top_header": "{prefix}--- Richest Players ---",
    "eco_top_entry": "{rank}. {player} - {amount}",
    "eco_top_empty": "{prefix}No player data found.",
    "eco_reload": "{prefix}Configuration reloaded.",
    "no_permission": "{prefix}You do not have permission to do that.",
    "player_only": "{prefix}This command can only be used by players.",
    "usage_error": "{prefix}Usage: {usage}",
    "error_generic": "{prefix}An internal error occurred. Please try again later.",
    "withdraw_success": "{prefix}You withdrew {amount} ({currency}) into a note.",
    "withdraw_disabled": "{prefix}Withdrawing this currency is disabled.",
    "withdraw_limit": "{prefix}Withdraw amount must be between {min} and {max}.",
    "withdraw_redeem": "{prefix}You redeemed a note worth {amount} ({currency}).",
}


class ConfigLoader:


    def __init__(self, data_folder: Path, logger: Logger) -> None:
        self._data_folder = data_folder
        self._logger = logger
        self._config: dict[str, Any] = {}
        self._messages: dict[str, str] = {}

    @property
    def database_config(self) -> dict[str, Any]:
        return self._config.get("database", _DEFAULT_CONFIG["database"])

    @property
    def economy_config(self) -> dict[str, Any]:
        return self._config.get("economy", _DEFAULT_CONFIG["economy"])

    @property
    def messages(self) -> dict[str, str]:
        return self._messages

    def load_all(self) -> None:
        self._data_folder.mkdir(parents=True, exist_ok=True)
        self._config = self._load_yaml("config.yml", _DEFAULT_CONFIG)
        self._messages = self._load_yaml("messages.yml", _DEFAULT_MESSAGES)

    def reload(self) -> None:
        self.load_all()

    def _load_yaml(self, filename: str, defaults: dict) -> dict:
        filepath = self._data_folder / filename
        if not filepath.exists():
            self._save_yaml(filepath, defaults)
            return dict(defaults)
        try:
            with filepath.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                self._logger.warning(f"Invalid {filename}, using defaults.")
                return dict(defaults)
            return self._deep_merge(defaults, data)
        except Exception as e:
            self._logger.error(f"Error loading {filename}: {e}")
            return dict(defaults)

    def _save_yaml(self, filepath: Path, data: dict) -> None:
        try:
            with filepath.open("w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        except Exception as e:
            self._logger.error(f"Error saving {filepath.name}: {e}")

    @staticmethod
    def _deep_merge(defaults: dict, overrides: dict) -> dict:
        result = dict(defaults)
        for key, value in overrides.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigLoader._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
