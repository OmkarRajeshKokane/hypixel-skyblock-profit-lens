#!/usr/bin/env python3
"""Find manual Hypixel SkyBlock Bazaar and NPC sell opportunities.

Uses only public, read-only Hypixel endpoints.  It never sends game actions and
does not require an API key.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_ROOT = "https://api.hypixel.net/v2"
BAZAAR_URL = f"{API_ROOT}/skyblock/bazaar"
ITEMS_URL = f"{API_ROOT}/resources/skyblock/items"
BAZAAR_TAX = 0.0125  # 1.25% on Bazaar sales. Kept configurable from the CLI.
CACHE_DIR = Path(__file__).parent / "data" / "cache"


@dataclass
class PriceRow:
    item_id: str
    item_name: str
    category: str
    stack_size: int
    npc_sell_price: float | None
    instant_buy_price: float | None
    instant_buy_available: float | None
    instant_sell_price: float | None
    instant_sell_available: float | None
    suggested_buy_order: float | None
    suggested_sell_order: float | None
    order_flip_profit_each: float | None
    bazaar_to_npc_profit_each: float | None
    weekly_liquidity: float
    buy_orders: int
    sell_orders: int


def money(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:,.2f}"


def cache_path(url: str) -> Path:
    name = "bazaar.json" if url == BAZAAR_URL else "items.json"
    return CACHE_DIR / name


def get_json(url: str, cache_minutes: float, refresh: bool) -> dict[str, Any]:
    """Fetch JSON with a small local cache to avoid unnecessary API traffic."""
    path = cache_path(url)
    max_age = cache_minutes * 60
    if not refresh and path.exists() and time.time() - path.stat().st_mtime < max_age:
        return json.loads(path.read_text(encoding="utf-8"))

    request = Request(url, headers={"User-Agent": "SkyBlockProfitScanner/1.0"})
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(f"Hypixel API returned HTTP {error.code} for {url}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach the Hypixel API: {error.reason}") from error

    if not payload.get("success"):
        raise RuntimeError(f"Hypixel API returned an unsuccessful response for {url}")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def best_quote(summary: list[dict[str, Any]], lowest: bool) -> tuple[float | None, float | None]:
    quotes = [order for order in summary if order.get("pricePerUnit") is not None]
    if not quotes:
        return None, None
    quote = min(quotes, key=lambda order: float(order["pricePerUnit"])) if lowest else max(
        quotes, key=lambda order: float(order["pricePerUnit"])
    )
    return float(quote["pricePerUnit"]), float(quote.get("amount", 0))


def price_step(price: float) -> float:
    """Bazaar prices support decimal coin amounts; keep a modest 0.1-coin step."""
    return 0.1 if price < 1_000_000 else 1.0


def build_rows(items: dict[str, Any], bazaar: dict[str, Any], tax: float) -> list[PriceRow]:
    item_info = {item["id"]: item for item in items.get("items", []) if item.get("id")}
    rows: list[PriceRow] = []

    for item_id, product in bazaar.get("products", {}).items():
        quick = product.get("quick_status", {})
        # Hypixel's Bazaar summaries are named from the player's action:
        # buy_summary is the order book used by "Buy Instantly" (your cost),
        # while sell_summary is used by "Sell Instantly" (your payout).
        instant_buy, instant_buy_available = best_quote(product.get("buy_summary", []), lowest=True)
        instant_sell, instant_sell_available = best_quote(product.get("sell_summary", []), lowest=False)
        info = item_info.get(item_id, {})
        npc_price = info.get("npc_sell_price")
        npc_sell = float(npc_price) if npc_price is not None else None
        # Bazaar materials, including Enchanted Sulphur Cube (PAPER), use the
        # normal SkyBlock/Minecraft stack capacity of 64 items.
        stack_size = 64

        buy_order = sell_order = order_profit = None
        if instant_buy is not None and instant_sell is not None:
            buy_order = instant_sell + price_step(instant_sell)
            sell_order = instant_buy - price_step(instant_buy)
            if sell_order > buy_order:
                order_profit = sell_order * (1 - tax) - buy_order

        npc_profit = None
        if npc_sell is not None and instant_buy is not None:
            npc_profit = npc_sell - instant_buy

        rows.append(
            PriceRow(
                item_id=item_id,
                item_name=info.get("name", item_id.replace("_", " ").title()),
                category=info.get("category", "Unknown"),
                stack_size=stack_size,
                npc_sell_price=npc_sell,
                instant_buy_price=instant_buy,
                instant_buy_available=instant_buy_available,
                instant_sell_price=instant_sell,
                instant_sell_available=instant_sell_available,
                suggested_buy_order=buy_order,
                suggested_sell_order=sell_order,
                order_flip_profit_each=order_profit,
                bazaar_to_npc_profit_each=npc_profit,
                weekly_liquidity=min(
                    float(quick.get("buyMovingWeek", 0)), float(quick.get("sellMovingWeek", 0))
                ),
                buy_orders=int(quick.get("buyOrders", 0)),
                sell_orders=int(quick.get("sellOrders", 0)),
            )
        )
    return rows


def actionable_rows(rows: list[PriceRow], args: argparse.Namespace) -> list[tuple[str, float, PriceRow]]:
    opportunities: list[tuple[str, float, PriceRow]] = []
    for row in rows:
        if row.weekly_liquidity < args.min_weekly_liquidity:
            continue
        if (
            row.order_flip_profit_each is not None
            and row.suggested_buy_order is not None
            and row.suggested_buy_order <= args.max_buy_price
            and row.order_flip_profit_each >= args.min_profit
        ):
            opportunities.append(("Bazaar order -> Bazaar order", row.order_flip_profit_each, row))
        if (
            row.bazaar_to_npc_profit_each is not None
            and row.instant_buy_price is not None
            and row.instant_buy_price <= args.max_buy_price
            and row.bazaar_to_npc_profit_each >= args.min_profit
        ):
            opportunities.append(("Bazaar instant buy -> NPC sell", row.bazaar_to_npc_profit_each, row))
    return sorted(opportunities, key=lambda entry: (entry[1], entry[2].weekly_liquidity), reverse=True)


def print_report(opportunities: list[tuple[str, float, PriceRow]], args: argparse.Namespace) -> None:
    print("\nHypixel SkyBlock manual profit scanner")
    print(f"Bazaar sale tax used: {args.bazaar_tax * 100:.2f}%")
    print("NPC price means the amount an NPC pays when you sell to it.\n")

    if not opportunities:
        print("No opportunities match the filters. Try --min-profit 0 or lower --min-weekly-liquidity.")
        return

    header = f"{'Route':34} {'Item':30} {'Profit/each':>14} {'Buy':>14} {'Sell':>14} {'At buy':>12} {'Weekly vol.':>14}"
    print(header)
    print("-" * len(header))
    for route, profit, row in opportunities[: args.top]:
        if route.startswith("Bazaar order"):
            buy, sell, available = row.suggested_buy_order, row.suggested_sell_order, None
        else:
            buy, sell, available = row.instant_buy_price, row.npc_sell_price, row.instant_buy_available
        print(
            f"{route:34.34} {row.item_name[:30]:30} {money(profit):>14} "
            f"{money(buy):>14} {money(sell):>14} {money(available):>12} {money(row.weekly_liquidity):>14}"
        )


def export_csv(rows: list[PriceRow], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    print(f"\nExported {len(rows):,} Bazaar products to {output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find Bazaar and NPC sell opportunities from official Hypixel data.")
    parser.add_argument("--top", type=int, default=25, help="number of ranked opportunities to print (default: 25)")
    parser.add_argument("--min-profit", type=float, default=100.0, help="minimum coins profit per item (default: 100)")
    parser.add_argument("--min-weekly-liquidity", type=float, default=10_000, help="minimum matched 7-day volume (default: 10000)")
    parser.add_argument("--max-buy-price", type=float, default=float("inf"), help="ignore opportunities that cost more per item")
    parser.add_argument("--bazaar-tax", type=float, default=BAZAAR_TAX, help="Bazaar sale tax as a decimal (default: 0.0125)")
    parser.add_argument("--cache-minutes", type=float, default=5, help="reuse API data this long (default: 5)")
    parser.add_argument("--refresh", action="store_true", help="ignore the local API cache")
    parser.add_argument("--export", type=Path, help="write every Bazaar product and price comparison to CSV")
    return parser.parse_args()


def main() -> int:
    # Some Windows terminals still default to cp1252. Replace unsupported item
    # name characters in terminal output instead of aborting a scan.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(errors="replace")
    args = parse_args()
    if not 0 <= args.bazaar_tax < 1:
        print("--bazaar-tax must be a decimal between 0 and 1.", file=sys.stderr)
        return 2
    try:
        items = get_json(ITEMS_URL, args.cache_minutes, args.refresh)
        bazaar = get_json(BAZAAR_URL, args.cache_minutes, args.refresh)
    except RuntimeError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    rows = build_rows(items, bazaar, args.bazaar_tax)
    print_report(actionable_rows(rows, args), args)
    if args.export:
        export_csv(rows, args.export)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
