# Hypixel SkyBlock profit scanner

A local, read-only command-line tool that uses the official Hypixel API to compare current Bazaar prices with official NPC sell values and rank potential manual flips.

It provides two routes:

1. **Bazaar buy order → Bazaar sell order** — suggests a price just above the current highest buy order and just below the lowest sell order. The displayed profit subtracts the Bazaar sale tax.
2. **Bazaar instant buy → NPC sell** — identifies items where an NPC's sell value is higher than the current lowest Bazaar sell offer.

The official item API exposes the amount an NPC will pay when you sell an item (`npc_sell_price`). It does **not** expose an authoritative NPC shop purchase price or every NPC location, so the scanner does not invent those values.

## Run

Requires Python 3.10 or later; there are no packages to install.

```powershell
.\run_scanner.bat --refresh --export .\data\skyblock_prices.csv
```

Useful filters:

```powershell
# Show 50 potentially liquid opportunities with at least 500 coins profit per item
.\run_scanner.bat --top 50 --min-profit 500 --min-weekly-liquidity 50000

# Limit suggestions to items costing at most 100,000 coins each
.\run_scanner.bat --max-buy-price 100000
```

`run_scanner.bat` uses the installed Python runtime automatically. If you already have `python` on your PATH, you can run `python .\skyblock_profit_scanner.py` instead.

The script caches API responses for five minutes by default. Use `--refresh` for current data.

## Interpretation

- **Buy** and **Sell** are coin prices per item, not per stack.
- **Instant-buy cost** is read from Hypixel's `buy_summary`; **instant-sell payout** is read from `sell_summary`. Despite the field names, this is the direction shown in the Bazaar interface.
- **At buy** is the quantity currently offered at the displayed instant-buy price. A very small amount can be an unusual or stale offer, so never assume the shown price applies to a large purchase.
- **Weekly vol.** is the smaller of the Bazaar's 7-day buy and sell volumes; it is a liquidity signal, not a guaranteed fill quantity.
- Bazaar order pricing changes before an order fills. Recheck the Bazaar screen before committing coins.
- The 1.25% Bazaar sales tax is configurable with `--bazaar-tax` in case Hypixel changes it.

This utility only reads public market information. It cannot interact with Minecraft, place orders, buy, sell, or automate gameplay.

## Live webpage

Start the dashboard:

```powershell
.\run_dashboard.bat
```

It opens `http://127.0.0.1:8000` automatically after two seconds. Keep the command window open while using the page; press `Ctrl+C` in that window when you are done. Do not open `web_dashboard.py` directly in a browser.

It presents two direct-profit sections, each in descending profit order:

- **Buy from NPC → Sell Instantly at Bazaar** compares coin-only NPC shop prices with the live Bazaar instant-sell payout, less the 1.25% Bazaar sale tax. It has an **Items per one-time buy** field (default 64, one stack) that recalculates total NPC cost, net Bazaar sale, and profit. The maintained NPC price list is in `npc_shop_prices.json`.
- **Craft enchanted item → Sell Instantly at Bazaar** calculates one enchanted craft from coin-purchased NPC materials and its net Bazaar sale. It shows both profit and loss, so a red number means the enchanted version is worth less than its base materials. Supported recipes are in `enchanted_recipes.json`.
- **Bazaar → NPC** compares the actual Bazaar **Buy Instantly** price with the amount an NPC pays immediately.

This avoids theoretical order-flip prices that may look reversed in the Bazaar interface. Select **Refresh live prices** to bypass the two-minute local cache.

The **Budget planners** accept your available coins and inventory-slot count for both direct routes separately: NPC-to-Bazaar and Bazaar-to-NPC. Each prioritizes profit per coin, favors full 64-item stacks, caps items at current immediate Bazaar order depth, and reports inventory fill. The two plans are alternatives, not combined allocations; prices can move or fill before you trade.

## Data sources

- [Hypixel Bazaar endpoint](https://api.hypixel.net/v2/skyblock/bazaar)
- [Hypixel SkyBlock item catalogue](https://api.hypixel.net/v2/resources/skyblock/items)
- [Hypixel API policies](https://developer.hypixel.net/policies/)
