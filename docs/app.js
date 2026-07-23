const route = document.body.dataset.route;
const configs = {
  bazaar_to_npc: { title: 'Bazaar → NPC maximum-profit opportunities', intro: 'Buy Instantly at the Bazaar and sell to an NPC.', buy: 'Bazaar Buy Instantly', market: 'current Bazaar offer depth', unit: 'items' },
  bazaar_to_bazaar: { title: 'Bazaar instant buy → instant sell opportunities', intro: 'Buy Instantly at the Bazaar, then sell Instantly at the Bazaar. Bazaar spread and sale tax usually mean no profitable instant flip is available.', buy: 'Bazaar Buy Instantly price', market: 'current Bazaar offer and demand depth', unit: 'items' },
  npc_to_bazaar: { title: 'NPC → Bazaar maximum-profit opportunities', intro: 'Buy coin-only items from an NPC and sell them instantly at the Bazaar.', buy: 'NPC purchase', market: 'current Bazaar demand depth', unit: 'items' },
  npc_to_npc: { title: 'NPC → NPC maximum-profit opportunities', intro: 'Buy an item from a listed NPC shop and sell it to an NPC. The public item catalogue provides the NPC sale payout but does not identify the specific selling NPC.', buy: 'NPC purchase', market: 'inventory capacity', unit: 'items' },
  crafting: { title: 'Crafting → Bazaar maximum-profit opportunities', intro: 'Compare buying recipe materials from an NPC or the Bazaar, craft the enchanted item, then sell it instantly at the Bazaar.', buy: 'ingredient cost per craft', market: 'available input materials and Bazaar output demand', unit: 'crafts' },
};
const BAZAAR = 'https://api.hypixel.net/v2/skyblock/bazaar';
const ITEMS = 'https://api.hypixel.net/v2/resources/skyblock/items';
const TAX = .0125;
const SETTINGS_KEY = 'skyblock_profit_calculator_settings_v4';
const NPC_DAILY_MARKS_KEY = 'skyblock_profit_npc_daily_marks_v1';
const body = document.querySelector('#results');
const summary = document.querySelector('#summary');
const status = document.querySelector('#status');
const refreshButton = document.querySelector('#refresh');
const resetNpcMarksButton = document.querySelector('#reset-npc-marks');
const coinsInput = document.querySelector('#available-coins');
const slotsInput = document.querySelector('#inventory-slots');
const exact = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });
let data = null;
let npcDailyMarks = {};

const coins = value => Math.abs(value) >= 1e6 ? `${(value / 1e6).toFixed(2)}M` : Math.abs(value) >= 1e3 ? `${(value / 1e3).toFixed(2)}K` : exact.format(value);

function quote(summary, lowest) {
  const orders = (summary || []).filter(order => Number.isFinite(Number(order.pricePerUnit)));
  if (!orders.length) return null;
  return orders.reduce((best, order) => lowest
    ? (Number(order.pricePerUnit) < Number(best.pricePerUnit) ? order : best)
    : (Number(order.pricePerUnit) > Number(best.pricePerUnit) ? order : best));
}

function restoreSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}');
    if (Number.isFinite(saved.coins) && saved.coins >= 0) coinsInput.value = saved.coins;
    if (Number.isFinite(saved.slots) && saved.slots >= 1) slotsInput.value = Math.min(36, Math.floor(saved.slots));
  } catch {}
}

function settings() {
  return {
    coins: Math.max(0, Number(coinsInput.value) || 0),
    slots: Math.max(1, Math.min(36, Math.floor(Number(slotsInput.value) || 1))),
  };
}

function saveSettings() { localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings())); }

function restoreNpcDailyMarks() {
  try {
    const saved = JSON.parse(localStorage.getItem(NPC_DAILY_MARKS_KEY) || '{}');
    if (saved && typeof saved === 'object' && !Array.isArray(saved)) npcDailyMarks = saved;
  } catch {}
}

function npcMarkKey(row) { return `npc:${String(row.daily_limit_key || row.item_name).toLowerCase()}`; }
function npcLimitUsed(row) { return Boolean(npcDailyMarks[npcMarkKey(row)]); }
function saveNpcDailyMarks() { localStorage.setItem(NPC_DAILY_MARKS_KEY, JSON.stringify(npcDailyMarks)); }

function stackDescription(items, stackSize = 64) {
  const stacks = Math.floor(items / stackSize);
  const remainder = items % stackSize;
  if (!remainder) return `${stacks} stack${stacks === 1 ? '' : 's'}`;
  return `${stacks} full stack${stacks === 1 ? '' : 's'} + ${remainder}`;
}

function calculate(row) {
  const { coins: availableCoins, slots } = settings();
  const stackSize = 64;
  const inputItemsPerUnit = Math.max(1, Math.floor(Number(row.input_items_per_unit) || 1));
  const inventoryLimit = Math.floor((stackSize * slots) / inputItemsPerUnit);
  const moneyLimit = Math.floor((availableCoins + 0.000001) / row.buy_price);
  const marketLimit = Math.floor(row.market_depth || 0);
  const units = Math.max(0, Math.min(inventoryLimit, moneyLimit, marketLimit));
  const totalCost = units * row.buy_price;
  const totalProfit = units * row.profit;

  if (row.kind === 'crafting') {
    const rawItems = units * inputItemsPerUnit;
    const rawStacks = stackDescription(rawItems, stackSize);
    return {
      ...row, units, totalCost, totalProfit,
      formula: `Buy ${exact.format(rawItems)}× ${row.ingredient_name} from ${row.buy_source} (${rawStacks}) → craft ${exact.format(units)}× ${row.item_name}; ${coins(row.buy_price)} × ${exact.format(units)} = ${coins(totalCost)}`,
    };
  }

  return {
    ...row, units, totalCost, totalProfit,
    formula: `${coins(row.buy_price)} × ${exact.format(units)} = ${coins(totalCost)} (${stackDescription(units, stackSize)} at ${stackSize} per stack)`,
  };
}

function addCell(row, value, className = '') {
  const cell = document.createElement('td');
  cell.textContent = value;
  cell.className = className;
  row.append(cell);
}

function render(rows) {
  const calculated = rows.map(calculate).sort((a, b) => b.totalProfit - a.totalProfit);
  body.replaceChildren();

  for (const item of calculated) {
    const row = document.createElement('tr');
    row.classList.toggle('limit-used', Boolean(item.uses_npc_purchase && npcLimitUsed(item)));
    addCell(row, item.action, 'action');
    addCell(row, item.item_name);
    addCell(row, coins(item.buy_price), 'coins');
    addCell(row, coins(item.sell_price), 'coins');
    addCell(row, coins(item.profit), 'coins profit');
    addCell(row, exact.format(item.units), 'coins');
    addCell(row, item.formula, 'formula');
    addCell(row, coins(item.totalProfit), 'coins profit');
    const markCell = document.createElement('td');
    if (item.uses_npc_purchase) {
      const mark = document.createElement('input');
      mark.type = 'checkbox';
      mark.checked = npcLimitUsed(item);
      mark.setAttribute('aria-label', `NPC daily limit used for ${item.daily_limit_key || item.item_name}`);
      mark.title = 'Mark this after you have bought the item from the NPC today.';
      mark.addEventListener('change', () => {
        npcDailyMarks[npcMarkKey(item)] = mark.checked;
        saveNpcDailyMarks();
        row.classList.toggle('limit-used', mark.checked);
      });
      markCell.append(mark);
    } else {
      markCell.textContent = '—';
    }
    row.append(markCell);
    body.append(row);
  }

  if (!calculated.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 9;
    cell.textContent = 'No profitable opportunities are available for this route right now.';
    row.append(cell);
    body.append(row);
  }

  const { coins: availableCoins, slots } = settings();
  summary.replaceChildren();
  for (const value of [`Available coins: ${coins(availableCoins)}`, `Inventory capacity: ${slots} slots`, `Showing ${exact.format(calculated.length)} opportunities`]) {
    const chip = document.createElement('span');
    chip.textContent = value;
    summary.append(chip);
  }
}

function createRows(items, bazaar) {
  const info = new Map((items.items || []).filter(item => item.id).map(item => [item.id, item]));
  return Object.entries(bazaar.products || {}).map(([id, product]) => {
    const buy = quote(product.buy_summary, true);
    const sell = quote(product.sell_summary, false);
    const item = info.get(id) || {};
    return {
      id,
      name: item.name || id.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, character => character.toUpperCase()),
      npc: Number(item.npc_sell_price),
      instantBuy: buy && Number(buy.pricePerUnit),
      instantBuyDepth: buy && Number(buy.amount),
      instantSell: sell && Number(sell.pricePerUnit),
      instantSellDepth: sell && Number(sell.amount),
    };
  });
}

function opportunities(rows, shops, recipes) {
  if (route === 'bazaar_to_npc') {
    return rows
      .filter(item => Number.isFinite(item.npc) && Number.isFinite(item.instantBuy) && item.npc > item.instantBuy)
      .map(item => ({
        action: `Buy ${item.name} from Bazaar → sell to NPC`,
        item_name: item.name,
        buy_price: item.instantBuy,
        sell_price: item.npc,
        profit: item.npc - item.instantBuy,
        market_depth: item.instantBuyDepth,
      }));
  }

  if (route === 'bazaar_to_bazaar') {
    return rows
      .filter(item => Number.isFinite(item.instantBuy) && Number.isFinite(item.instantSell))
      .map(item => {
        const buy = item.instantBuy;
        const sell = item.instantSell * (1 - TAX);
        return {
          action: `Buy ${item.name} Instantly at Bazaar → sell Instantly at Bazaar`,
          item_name: item.name,
          buy_price: buy,
          sell_price: sell,
          profit: sell - buy,
          market_depth: Math.min(Math.floor(item.instantBuyDepth || 0), Math.floor(item.instantSellDepth || 0)),
        };
      })
      .filter(item => item.profit > 0 && item.market_depth > 0);
  }

  const shopByName = new Map(shops.map(shop => [shop.item_name.toLowerCase(), shop]));
  if (route === 'npc_to_npc') {
    return rows
      .filter(item => shopByName.has(item.name.toLowerCase()) && Number.isFinite(item.npc) && item.npc > 0)
      .map(item => {
        const shop = shopByName.get(item.name.toLowerCase());
        const buy = Number(shop.npc_buy_price);
        return {
          action: `Buy ${item.name} from ${shop.npc} → sell to an NPC`,
          item_name: item.name,
          buy_price: buy,
          sell_price: item.npc,
          profit: item.npc - buy,
          market_depth: 999999999,
          uses_npc_purchase: true,
          daily_limit_key: item.name,
        };
      })
      .filter(item => item.profit > 0);
  }

  if (route === 'npc_to_bazaar') {
    return rows
      .filter(item => shopByName.has(item.name.toLowerCase()) && Number.isFinite(item.instantSell))
      .map(item => {
        const shop = shopByName.get(item.name.toLowerCase());
        const buy = Number(shop.npc_buy_price);
        const sell = item.instantSell * (1 - TAX);
        return {
          action: `Buy ${item.name} from ${shop.npc} → sell instantly at Bazaar`,
          item_name: item.name,
          buy_price: buy,
          sell_price: sell,
          profit: sell - buy,
          market_depth: item.instantSellDepth,
          uses_npc_purchase: true,
          daily_limit_key: item.name,
        };
      })
      .filter(item => item.profit > 0);
  }

  const byName = new Map(rows.map(item => [item.name.toLowerCase(), item]));
  const plans = [];
  for (const recipe of recipes) {
    const amount = Math.max(1, Number(recipe.amount));
    const ingredient = byName.get(recipe.base_item.toLowerCase());
    const output = byName.get(recipe.crafted_item.toLowerCase());
    if (!ingredient || !output || !Number.isFinite(output.instantSell)) continue;

    const netOutputSale = output.instantSell * (1 - TAX);
    const addPlan = (buySource, ingredientPrice, ingredientCraftLimit) => {
      if (!Number.isFinite(ingredientPrice)) return;
      const buy = ingredientPrice * amount;
      const profit = netOutputSale - buy;
      const outputDemand = Math.floor(output.instantSellDepth || 0);
      const marketDepth = Math.min(outputDemand, ingredientCraftLimit);
      if (profit <= 0 || marketDepth <= 0) return;
      plans.push({
        kind: 'crafting',
        action: `Buy ${amount}× ${ingredient.name} from ${buySource} → craft ${output.name} → sell instantly at Bazaar`,
        item_name: output.name,
        ingredient_name: ingredient.name,
        buy_source: buySource,
        input_items_per_unit: amount,
        buy_price: buy,
        sell_price: netOutputSale,
        profit,
        market_depth: marketDepth,
        uses_npc_purchase: buySource.startsWith('NPC ('),
        daily_limit_key: ingredient.name,
      });
    };

    const shop = shopByName.get(recipe.base_item.toLowerCase());
    if (shop) addPlan(`NPC (${shop.npc})`, Number(shop.npc_buy_price), Infinity);
    if (Number.isFinite(ingredient.instantBuy)) {
      addPlan('Bazaar (Buy Instantly)', ingredient.instantBuy, Math.floor((ingredient.instantBuyDepth || 0) / amount));
    }
  }
  return plans;
}

function initializeAds() {
  const isLocalPreview = ['localhost', '127.0.0.1'].includes(location.hostname);
  if (isLocalPreview) {
    for (const placeholder of document.querySelectorAll('[data-ad-slot]')) {
      placeholder.hidden = false;
      placeholder.classList.add('ad-preview');
      placeholder.textContent = `Ad preview: ${placeholder.dataset.adSlot.replace('_', ' ')} — live ads appear after public hosting and AdSense approval`;
    }
    return;
  }
  const ads = window.SKYBLOCK_ADSENSE || {};
  const client = String(ads.client || '');
  if (!/^ca-pub-\d+$/.test(client)) return;
  for (const placeholder of document.querySelectorAll('[data-ad-slot]')) {
    const slot = String((ads.slots || {})[placeholder.dataset.adSlot] || '');
    if (!/^\d+$/.test(slot)) { placeholder.hidden = true; continue; }
    const unit = document.createElement('ins');
    unit.className = 'adsbygoogle';
    unit.style.display = 'block';
    unit.dataset.adClient = client;
    unit.dataset.adSlot = slot;
    unit.dataset.adFormat = 'auto';
    unit.dataset.fullWidthResponsive = 'true';
    placeholder.replaceChildren(unit);
    (window.adsbygoogle = window.adsbygoogle || []).push({});
  }
}

async function load() {
  refreshButton.disabled = true;
  status.className = '';
  status.textContent = 'Loading live Hypixel market data...';
  try {
    const [items, bazaar, shops, recipes] = await Promise.all([
      fetch(ITEMS).then(response => response.json()),
      fetch(BAZAAR).then(response => response.json()),
      fetch('./npc_shop_prices.json').then(response => response.json()),
      fetch('./enchanted_recipes.json').then(response => response.json()),
    ]);
    if (!items.success || !bazaar.success) throw Error('Hypixel API did not return market data.');
    data = opportunities(createRows(items, bazaar), shops, recipes);
    render(data);
    status.textContent = `${exact.format(data.length)} opportunities | updated ${new Date().toLocaleTimeString()}`;
  } catch (error) {
    status.className = 'error';
    status.textContent = `Could not load live data: ${error.message}`;
  } finally {
    refreshButton.disabled = false;
  }
}

const config = configs[route];
document.querySelector(`[data-route-link="${route}"]`).classList.add('active');
document.querySelector('#intro').textContent = config.intro;
document.querySelector('#method-title').textContent = config.title;
document.querySelector('#action-header').textContent = route === 'crafting' ? 'What to buy → craft → sell' : 'Plan';
document.querySelector('#buy-header').textContent = route === 'crafting' ? 'Ingredient cost / craft' : route === 'bazaar_to_bazaar' ? 'Instant-buy cost' : route === 'npc_to_npc' ? 'NPC buy / unit' : 'Buy / unit';
document.querySelector('#sell-header').textContent = route === 'crafting' ? 'Net Bazaar sale / craft' : route === 'bazaar_to_bazaar' ? 'Net instant-sell payout' : route === 'npc_to_npc' ? 'NPC sell / unit' : 'Sell / unit';
document.querySelector('#profit-header').textContent = route === 'crafting' ? 'Profit / craft' : 'Profit / unit';
document.querySelector('#max-header').textContent = route === 'crafting' ? 'Max crafts' : 'Max units';
document.querySelector('#daily-header').textContent = 'NPC daily limit used?';
document.querySelector('#formula-note').textContent = route === 'crafting'
  ? 'For every plan independently: maximum crafts = min(floor((64 × inventory slots) ÷ raw materials per craft), floor(available coins ÷ ingredient cost per craft), available Bazaar materials when buying there, Bazaar output demand).'
  : `For every row independently: maximum ${config.unit} = min(stack size × inventory slots, floor(available coins ÷ ${config.buy} price), ${config.market}). Total profit = maximum ${config.unit} × profit per unit.`;
refreshButton.addEventListener('click', load);
resetNpcMarksButton.addEventListener('click', () => {
  if (!confirm('Clear every NPC daily-limit mark saved in this browser?')) return;
  npcDailyMarks = {};
  saveNpcDailyMarks();
  if (data) render(data);
});
for (const input of [coinsInput, slotsInput]) input.addEventListener('input', () => { saveSettings(); if (data) render(data); });
restoreSettings();
restoreNpcDailyMarks();
initializeAds();
load();
