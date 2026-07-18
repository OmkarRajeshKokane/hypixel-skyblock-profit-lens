#!/usr/bin/env python3
"""Local multi-page Hypixel SkyBlock manual profit dashboard."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from skyblock_profit_scanner import BAZAAR_TAX, BAZAAR_URL, ITEMS_URL, build_rows, get_json


SHOP_PRICES_FILE = Path(__file__).with_name("npc_shop_prices.json")
RECIPES_FILE = Path(__file__).with_name("enchanted_recipes.json")
AD_CONFIG_FILE = Path(__file__).with_name("adsense_config.js")


PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, system-ui, sans-serif; }
    body { max-width: 1400px; margin: 0 auto; padding: 28px 18px; background: #10151c; color: #eef3f8; }
    h1 { margin: 0; font-size: clamp(1.55rem, 4vw, 2.25rem); }
    h2 { margin-top: 28px; }
    p { color: #aab6c4; margin: 8px 0 18px; }
    nav { display: flex; flex-wrap: wrap; gap: 8px; margin: 18px 0; }
    nav a { color: #b9c6d5; text-decoration: none; padding: 8px 11px; border: 1px solid #2a3542; border-radius: 7px; }
    nav a.active { color: #07140d; background: #45b97c; border-color: #45b97c; font-weight: 700; }
    button { border: 0; border-radius: 8px; background: #45b97c; color: #07140d; font-weight: 700; padding: 10px 14px; cursor: pointer; }
    button:disabled { opacity: .6; cursor: wait; }
    #status { margin-left: 12px; color: #aab6c4; font-size: .9rem; }
    .settings { display: flex; align-items: center; flex-wrap: wrap; gap: 12px 18px; padding: 12px; border: 1px solid #2a3542; border-radius: 8px; }
    .settings label { display: flex; align-items: center; gap: 8px; color: #c8d4df; }
    .settings input { width: 104px; border: 1px solid #3a4a5b; border-radius: 6px; background: #18212b; color: #eef3f8; padding: 7px; font: inherit; }
    .settings small { color: #8e9baa; flex-basis: 100%; }
    .summary { display: flex; flex-wrap: wrap; gap: 10px; margin: 12px 0; color: #c8d4df; }
    .summary span { padding: 8px 10px; background: #18212b; border-radius: 7px; font-variant-numeric: tabular-nums; }
    .table-wrap { margin-top: 14px; border: 1px solid #2a3542; border-radius: 10px; overflow-x: auto; }
    table { width: 100%; min-width: 1080px; border-collapse: collapse; }
    th, td { padding: 12px 10px; text-align: left; border-bottom: 1px solid #25303b; }
    th { background: #18212b; color: #b9c6d5; font-size: .78rem; letter-spacing: .06em; text-transform: uppercase; }
    tr:last-child td { border-bottom: 0; }
    tr:hover td { background: #17212b; }
    .coins { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
    .profit { color: #72e3a4; font-weight: 700; }
    .formula { color: #a9caff; white-space: nowrap; }
    .error { color: #ff8e8e; }
    .ad-slot { min-height: 100px; display: grid; place-items: center; margin: 18px 0; border: 1px dashed #405266; border-radius: 8px; background: #121c26; color: #7f91a4; font-size: .78rem; letter-spacing: .08em; text-transform: uppercase; }
    .ad-slot:has(ins) { display: block; min-height: 0; border-style: solid; }
    .ad-rail { display: none; position: fixed; top: 150px; width: 140px; min-height: 600px; z-index: 2; }
    .ad-rail-left { left: max(12px, calc(50vw - 900px)); }
    .ad-rail-right { right: max(12px, calc(50vw - 900px)); }
    @media (min-width: 1750px) { .ad-rail { display: grid; } }
    footer { margin: 28px 0 4px; color: #8e9baa; font-size: .85rem; }
    footer a { color: #a9caff; }
  </style>
</head>
<body data-route="__ROUTE__">
  <h1>SkyBlock Profit Calculator</h1>
  <nav aria-label="Profit methods">
    <a href="/" data-route-link="bazaar_to_npc">Bazaar → NPC</a>
    <a href="/npc-to-bazaar" data-route-link="npc_to_bazaar">NPC → Bazaar</a>
    <a href="/crafting" data-route-link="crafting">Crafting → Bazaar</a>
  </nav>
  <p id="intro"></p>
  <button id="refresh">Refresh live prices</button><span id="status">Loading...</span>
  <div class="ad-slot" data-ad-slot="header"><span>Advertisement</span></div>
  <aside class="ad-slot ad-rail ad-rail-left" data-ad-slot="left_rail"><span>Advertisement</span></aside>
  <aside class="ad-slot ad-rail ad-rail-right" data-ad-slot="right_rail"><span>Advertisement</span></aside>

  <h2>Calculator settings</h2>
  <div class="settings">
    <label>Available coins <input id="available-coins" type="number" min="0" step="1" value="100000"></label>
    <label>Inventory slots <input id="inventory-slots" type="number" min="1" max="36" step="1" value="36"></label>
    <small>These settings are saved in this browser. Each row is calculated separately; it does not split your coins between rows.</small>
  </div>
  <div class="ad-slot" data-ad-slot="settings"><span>Advertisement</span></div>

  <h2 id="method-title"></h2>
  <p id="formula-note"></p>
  <div id="summary" class="summary"></div>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Item</th><th class="coins">Buy / unit</th><th class="coins">Sell / unit</th><th class="coins">Profit / unit</th><th class="coins">Max units</th><th>Purchase calculation</th><th class="coins">Total profit</th></tr></thead>
      <tbody id="results"></tbody>
    </table>
  </div>

  <div class="ad-slot" data-ad-slot="footer"><span>Advertisement</span></div>
  <footer>Market data is informational only. <a href="/privacy">Privacy policy</a></footer>
  <script src="/adsense-config.js"></script>
  <script>
    const route = document.body.dataset.route;
    const configurations = {
      bazaar_to_npc: {
        title: 'Bazaar → NPC maximum-profit opportunities',
        intro: 'Buy Instantly at the Bazaar and sell to an NPC.',
        buy: 'Bazaar buy', sell: 'NPC sell', market: 'current Bazaar top-price offer depth', unit: 'items'
      },
      npc_to_bazaar: {
        title: 'NPC → Bazaar maximum-profit opportunities',
        intro: 'Buy coin-only items from an NPC and sell them instantly at the Bazaar.',
        buy: 'NPC buy', sell: 'net Bazaar sale', market: 'current Bazaar top-price demand', unit: 'items'
      },
      crafting: {
        title: 'Crafting → Bazaar maximum-profit opportunities',
        intro: 'Buy recipe inputs from an NPC, craft the enchanted item, then sell it instantly at the Bazaar.',
        buy: 'NPC recipe cost', sell: 'net Bazaar sale', market: 'current Bazaar top-price demand', unit: 'crafts'
      },
    };
    const config = configurations[route];
    const body = document.getElementById('results');
    const summary = document.getElementById('summary');
    const status = document.getElementById('status');
    const refreshButton = document.getElementById('refresh');
    const coinsInput = document.getElementById('available-coins');
    const slotsInput = document.getElementById('inventory-slots');
    const SETTINGS_KEY = 'skyblock_profit_calculator_settings_v2';
    const exact = new Intl.NumberFormat(undefined, {maximumFractionDigits: 2});
    let data = null;
    const coins = value => {
      const absolute = Math.abs(value);
      if (absolute >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
      if (absolute >= 1_000) return `${(value / 1_000).toFixed(2)}K`;
      return exact.format(value);
    };
    const cell = (row, value, className = '') => {
      const td = document.createElement('td'); td.textContent = value; td.className = className; row.append(td);
    };
    function initializeAds() {
      const ads = window.SKYBLOCK_ADSENSE || {};
      const client = String(ads.client || '');
      if (!/^ca-pub-\d+$/.test(client)) return;
      if (!document.querySelector('script[data-adsense-loader]')) {
        const loader = document.createElement('script'); loader.async = true; loader.dataset.adsenseLoader = 'true';
        loader.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${client}`;
        loader.crossOrigin = 'anonymous'; document.head.append(loader);
      }
      for (const placeholder of document.querySelectorAll('[data-ad-slot]')) {
        const slot = String((ads.slots || {})[placeholder.dataset.adSlot] || '');
        if (!/^\d+$/.test(slot)) continue;
        const unit = document.createElement('ins'); unit.className = 'adsbygoogle'; unit.style.display = 'block';
        unit.dataset.adClient = client; unit.dataset.adSlot = slot; unit.dataset.adFormat = 'auto'; unit.dataset.fullWidthResponsive = 'true';
        placeholder.replaceChildren(unit);
        (window.adsbygoogle = window.adsbygoogle || []).push({});
      }
    }
    function restoreSettings() {
      try {
        const saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}');
        if (Number.isFinite(saved.coins) && saved.coins >= 0) coinsInput.value = saved.coins;
        if (Number.isFinite(saved.slots) && saved.slots >= 1) slotsInput.value = Math.min(36, Math.floor(saved.slots));
      } catch {}
    }
    function currentSettings() {
      return {
        coins: Math.max(0, Number(coinsInput.value) || 0),
        slots: Math.max(1, Math.min(36, Math.floor(Number(slotsInput.value) || 1))),
      };
    }
    function saveSettings() {
      const current = currentSettings();
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(current));
    }
    function calculate(row) {
      const {coins: availableCoins, slots} = currentSettings();
      const stackSize = Math.max(1, Math.floor(Number(row.stack_size) || 64));
      const inventoryLimit = stackSize * slots;
      const moneyLimit = Math.floor((availableCoins + 0.000001) / row.buy_price);
      const marketLimit = Math.floor(row.market_depth || 0);
      const units = Math.max(0, Math.min(inventoryLimit, moneyLimit, marketLimit));
      const stacks = Math.floor(units / stackSize);
      const remainder = units % stackSize;
      const stackText = remainder ? `${stacks} full stack${stacks === 1 ? '' : 's'} + ${remainder}` : `${stacks} stack${stacks === 1 ? '' : 's'}`;
      const totalCost = units * row.buy_price;
      return {...row, units, stackSize, totalCost, totalProfit: units * row.profit, formula: `${coins(row.buy_price)} × ${exact.format(units)} = ${coins(totalCost)} (${stackSize} per stack × ${stackText})`};
    }
    function render(rows) {
      const calculated = rows.map(calculate).sort((a, b) => b.totalProfit - a.totalProfit);
      body.replaceChildren();
      for (const item of calculated) {
        const row = document.createElement('tr');
        cell(row, item.item_name);
        cell(row, coins(item.buy_price), 'coins');
        cell(row, coins(item.sell_price), 'coins');
        cell(row, coins(item.profit), 'coins profit');
        cell(row, exact.format(item.units), 'coins');
        cell(row, item.formula, 'formula');
        cell(row, coins(item.totalProfit), 'coins profit');
        body.append(row);
      }
      if (!calculated.length) {
        const row = document.createElement('tr'); const empty = document.createElement('td');
        empty.colSpan = 7; empty.textContent = 'No profitable opportunities are available for this route right now.';
        row.append(empty); body.append(row);
      }
      const {coins: availableCoins, slots} = currentSettings();
      summary.replaceChildren();
      for (const value of [`Available coins: ${coins(availableCoins)}`, `Inventory capacity: ${slots} slots`, `Showing ${exact.format(calculated.length)} opportunities`]) {
        const chip = document.createElement('span'); chip.textContent = value; summary.append(chip);
      }
    }
    async function load(force = false) {
      refreshButton.disabled = true; status.className = ''; status.textContent = 'Loading market data...';
      try {
        const response = await fetch('/api/opportunities' + (force ? '?refresh=1' : ''));
        const responseData = await response.json();
        if (!response.ok) throw new Error(responseData.error || 'Could not load opportunities');
        data = responseData[route];
        render(data);
        status.textContent = `${exact.format(data.length)} opportunities | updated ${new Date(responseData.updated_at).toLocaleTimeString()}`;
      } catch (error) { status.textContent = error.message; status.className = 'error'; }
      finally { refreshButton.disabled = false; }
    }
    document.querySelector(`[data-route-link="${route}"]`).classList.add('active');
    document.getElementById('intro').textContent = config.intro;
    document.getElementById('method-title').textContent = config.title;
    document.getElementById('formula-note').textContent = `For every row independently: maximum ${config.unit} = min(stack size × inventory slots, floor(available coins ÷ ${config.buy} price), ${config.market}). Total profit = maximum ${config.unit} × profit per unit.`;
    refreshButton.addEventListener('click', () => load(true));
    for (const input of [coinsInput, slotsInput]) input.addEventListener('input', () => { saveSettings(); if (data) render(data); });
    restoreSettings();
    initializeAds();
    load();
  </script>
</body>
</html>"""


def bazaar_to_npc_opportunities(rows: list) -> list[dict[str, float | str | int]]:
    results: list[dict[str, float | str | int]] = []
    for row in rows:
        if row.bazaar_to_npc_profit_each is not None and row.bazaar_to_npc_profit_each > 0:
            results.append({
                "item_name": row.item_name,
                "buy_price": row.instant_buy_price or 0,
                "sell_price": row.npc_sell_price or 0,
                "profit": row.bazaar_to_npc_profit_each,
                "market_depth": row.instant_buy_available or 0,
                "stack_size": row.stack_size,
            })
    return sorted(results, key=lambda item: float(item["profit"]), reverse=True)


def npc_to_bazaar_opportunities(rows: list) -> list[dict[str, float | str | int]]:
    shops = json.loads(SHOP_PRICES_FILE.read_text(encoding="utf-8"))
    shop_by_name = {entry["item_name"].casefold(): entry for entry in shops}
    results: list[dict[str, float | str | int]] = []
    for row in rows:
        shop = shop_by_name.get(row.item_name.casefold())
        if shop is None or row.instant_sell_price is None:
            continue
        buy_price = float(shop["npc_buy_price"])
        sell_price = row.instant_sell_price * (1 - BAZAAR_TAX)
        profit = sell_price - buy_price
        if profit > 0:
            results.append({
                "item_name": row.item_name,
                "buy_price": buy_price,
                "sell_price": sell_price,
                "profit": profit,
                "market_depth": row.instant_sell_available or 0,
                "stack_size": row.stack_size,
            })
    return sorted(results, key=lambda item: float(item["profit"]), reverse=True)


def crafting_opportunities(rows: list) -> list[dict[str, float | str | int]]:
    shops = json.loads(SHOP_PRICES_FILE.read_text(encoding="utf-8"))
    recipes = json.loads(RECIPES_FILE.read_text(encoding="utf-8"))
    npc_price = {entry["item_name"].casefold(): float(entry["npc_buy_price"]) for entry in shops}
    bazaar_by_name = {row.item_name.casefold(): row for row in rows}
    results: list[dict[str, float | str | int]] = []
    for recipe in recipes:
        base_name = str(recipe["base_item"])
        crafted_name = str(recipe["crafted_item"])
        materials = int(recipe["amount"])
        input_price = npc_price.get(base_name.casefold())
        crafted = bazaar_by_name.get(crafted_name.casefold())
        if input_price is None or crafted is None or crafted.instant_sell_price is None:
            continue
        buy_price = input_price * materials
        sell_price = crafted.instant_sell_price * (1 - BAZAAR_TAX)
        profit = sell_price - buy_price
        if profit > 0:
            results.append({
                "item_name": f"{crafted.item_name} ({materials}x {base_name})",
                "buy_price": buy_price,
                "sell_price": sell_price,
                "profit": profit,
                "market_depth": crafted.instant_sell_available or 0,
                "stack_size": crafted.stack_size,
            })
    return sorted(results, key=lambda item: float(item["profit"]), reverse=True)


def market_sections(refresh: bool) -> dict[str, list[dict[str, float | str | int]]]:
    items = get_json(ITEMS_URL, cache_minutes=2, refresh=refresh)
    bazaar = get_json(BAZAAR_URL, cache_minutes=2, refresh=refresh)
    rows = build_rows(items, bazaar, BAZAAR_TAX)
    return {
        "bazaar_to_npc": bazaar_to_npc_opportunities(rows),
        "npc_to_bazaar": npc_to_bazaar_opportunities(rows),
        "crafting": crafting_opportunities(rows),
    }


PRIVACY_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Privacy Policy</title>
<style>body{max-width:800px;margin:0 auto;padding:28px 18px;font-family:system-ui,sans-serif;line-height:1.55;background:#10151c;color:#eef3f8}a{color:#a9caff}p{color:#c8d4df}</style></head>
<body><h1>Privacy Policy</h1><p>This calculator requests public Hypixel market data to display profit estimates. It stores only calculator settings in your browser's local storage.</p><p>If advertising is enabled, advertising providers such as Google may use cookies or similar technologies to serve and measure ads. Review the advertising provider's privacy policy for details and available controls.</p><p><a href="/">Return to calculator</a></p></body></html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    PAGE_ROUTES = {
        "/": ("bazaar_to_npc", "SkyBlock Bazaar to NPC Profit Calculator"),
        "/npc-to-bazaar": ("npc_to_bazaar", "SkyBlock NPC to Bazaar Profit Calculator"),
        "/crafting": ("crafting", "SkyBlock Crafting to Bazaar Profit Calculator"),
    }

    def send_json(self, status: int, payload: dict[str, object]) -> None:
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:  # noqa: N802
        request = urlparse(self.path)
        if request.path == "/adsense-config.js":
            content = AD_CONFIG_FILE.read_bytes() if AD_CONFIG_FILE.exists() else b"window.SKYBLOCK_ADSENSE = {};"
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        if request.path == "/privacy":
            content = PRIVACY_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        if request.path in self.PAGE_ROUTES:
            route, title = self.PAGE_ROUTES[request.path]
            content = PAGE.replace("__ROUTE__", route).replace("__TITLE__", title).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        if request.path == "/api/opportunities":
            try:
                refresh = parse_qs(request.query).get("refresh") == ["1"]
                self.send_json(200, {**market_sections(refresh), "updated_at": __import__("time").time() * 1000})
            except RuntimeError as error:
                self.send_json(503, {"error": str(error)})
            return
        self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local SkyBlock profit dashboard.")
    parser.add_argument("--port", type=int, default=8000, help="local port to use (default: 8000)")
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), DashboardHandler)
    print(f"Open http://127.0.0.1:{args.port} in your browser. Press Ctrl+C to stop the server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
