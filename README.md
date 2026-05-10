# JWEconomy

JWEconomy is a robust, lightweight, and highly performant economy plugin for Minecraft Bedrock, built specifically for the **Endstone API**. It provides server administrators with a fully-featured monetary system that is easy to manage, fast, and scalable. 

Whether you are running a small survival server or a massive network, JWEconomy provides the foundation you need for an engaging in-game economy.

## 🌟 Key Features

- **High-Performance SQLite Database:** Balances and transactions are stored using asynchronous SQLite (WAL mode) to ensure the server never lags, even during heavy transaction periods.
- **Smart Memory Caching:** Player balances are cached in memory for instant retrieval, significantly reducing database read operations.
- **Player-to-Player Transfers (`/pay`):** Players can seamlessly send currency to one another.
- **Configurable Taxation:** Server owners can implement a tax percentage on all `/pay` transfers to act as an economy money sink and combat inflation.
- **Top Balance Leaderboard (`/eco top`):** A competitive ranking system that shows the richest players on the server.
- **Full Localization Support:** Every single message, including the currency symbol and format, can be customized in the `messages.yml` file.
- **Developer-Friendly API:** Built with an asynchronous API, making it incredibly easy for other plugins (like Shops or Auction Houses) to hook into and use the economy.

---

## 🛠️ Commands & Permissions

| Command | Permission Node | Description |
|---|---|---|
| `/balance [player]` | `jweconomy.command.balance` | Check your own balance or the balance of another player. |
| `/pay <player> <amount>` | `jweconomy.command.pay` | Transfer money from your account to another player. |
| `/eco top` | `jweconomy.command.eco` | View the top richest players on the server. |
| `/eco give <player> <amount>`| `jweconomy.command.eco` | **(Admin)** Add money to a player's balance. |
| `/eco take <player> <amount>`| `jweconomy.command.eco` | **(Admin)** Deduct money from a player's balance. |
| `/eco set <player> <amount>` | `jweconomy.command.eco` | **(Admin)** Set a player's balance to an exact amount. |
| `/eco reload` | `jweconomy.command.eco` | **(Admin)** Reload the configuration and message files. |

*Note: Admin commands work on players even if they are offline, using robust UUID tracking.*

---

## ⚙️ Configuration (`config.yml`)

When you first run the plugin, a `config.yml` file is generated in the plugin's data folder. 

```yaml
database:
  filename: jweconomy.db # The SQLite database file name.

economy:
  starting_balance: 1000.0 # How much money new players start with.
  currency_symbol: "$" # The symbol displayed before/after amounts.
  currency_name: "Coins" # The name of the currency.
  currency_name_plural: "Coins" # Plural name of the currency.
  max_balance: 1000000000.0 # The maximum allowed balance.
  min_transaction: 0.01 # Minimum amount that can be transferred.
  transfer_tax_percent: 5.0 # Tax percentage (0-100) applied to /pay. Example: 5% tax.
  top_entries_per_page: 10 # How many players to show per page in /eco top.
```

---

## 💻 Developer API

JWEconomy exposes a robust asynchronous API for other developers to integrate economy features into their own plugins (such as Shops, Markets, etc.).

### 1. Getting the API Instance
```python
economy_plugin = self.server.plugin_manager.get_plugin("jweconomy")
if not economy_plugin:
    self.logger.error("JWEconomy is not installed!")
    return

# Get the API instance
api = economy_plugin.get_api()
```

### 2. Using the API Methods

**Important:** Because JWEconomy uses an asynchronous database, all API methods are `async`. You must `await` them inside an asynchronous context.

#### Check a Player's Balance
```python
# Returns a float representing the player's balance
balance = await api.get_balance(player_uuid)
```

#### Check if a Player has Enough Money
```python
# Returns True if the player has at least 500 coins, False otherwise
if await api.has_balance(player_uuid, 500.0):
    print("Player has enough money!")
```

#### Add to a Player's Balance
```python
# Adds 100 to the balance and returns the new total balance
new_balance = await api.add_balance(player_uuid, 100.0)
```

#### Remove from a Player's Balance
```python
# Removes 50 from the balance. Returns the new balance, or None if the player doesn't have enough.
new_balance = await api.remove_balance(player_uuid, 50.0)
```

#### Set a Player's Exact Balance
```python
# Overwrites the balance to exactly 1000
new_balance = await api.set_balance(player_uuid, 1000.0)
```

#### Transfer Money Between Players
```python
# Safely transfers 200 from sender to receiver, applying any configured taxes.
result = await api.transfer_balance(sender_uuid, receiver_uuid, 200.0)

if result.success:
    print(f"Transferred! Sender new balance: {result.sender_new_balance}")
    print(f"Tax paid to server: {result.tax_amount}")
else:
    print(f"Transfer failed: {result.error}")
```

#### Get Currency Formatting
```python
symbol = api.currency_symbol # e.g. "$"
name = api.currency_name # e.g. "Coins"
```
