const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const docs = path.join(__dirname, '../docs');
const source = fs.readFileSync(path.join(docs, 'app.js'), 'utf8');
const items = { success: true, items: [{ id: 'RAW', name: 'Raw', npc_sell_price: 12 }, { id: 'CRAFT', name: 'Craft', npc_sell_price: 1 }] };
const bazaar = { success: true, products: {
  RAW: { buy_summary: [{ pricePerUnit: 10, amount: 500 }], sell_summary: [{ pricePerUnit: 8, amount: 300 }] },
  CRAFT: { buy_summary: [{ pricePerUnit: 650, amount: 20 }], sell_summary: [{ pricePerUnit: 600, amount: 10 }] }
} };
const shops = [{ item_name: 'Raw', npc_buy_price: 5, npc: 'Example' }];
const recipes = [{ base_item: 'Raw', crafted_item: 'Craft', amount: 10 }];
function element(value = '') {
  return { value, textContent: '', children: [], dataset: {}, classList: { add() {}, toggle() {} },
    append(child) { this.children.push(child); }, replaceChildren(...children) { this.children = children; },
    setAttribute() {}, addEventListener() {} };
}
function harness(route = 'bazaar_to_npc', storageBlocked = false) {
  const nodes = new Map();
  const get = id => { if (!nodes.has(id)) nodes.set(id, element()); return nodes.get(id); };
  get('#available-coins').value = '1000'; get('#inventory-slots').value = '2'; get('#bazaar-tax').value = '1.25';
  const context = vm.createContext({ Intl, Date, Number, Math, JSON, Map, Error, AbortController, setTimeout, clearTimeout,
    document: { body: { dataset: { route } }, querySelector: get, querySelectorAll: () => [], createElement: element },
    localStorage: { getItem: () => null, setItem: () => { if (storageBlocked) throw Error('Storage denied'); } },
    location: { hostname: 'localhost' }, window: {}, confirm: () => true,
    fetch: async url => ({ ok: true, json: async () => String(url).includes('/resources/') ? items : String(url).endsWith('/bazaar') ? bazaar : String(url).includes('npc_shop') ? shops : recipes })
  });
  // Exercise initialization but control loading explicitly in each test.
  vm.runInContext(source.replace(/load\(\);\s*$/, ''), context);
  return { context, get, run: code => vm.runInContext(code, context) };
}
test('all five modes load and render without exceptions', async () => {
  for (const route of ['bazaar_to_npc','bazaar_to_bazaar','npc_to_bazaar','npc_to_npc','crafting']) {
    const h = harness(route); await h.run('load()');
    assert.match(h.get('#status').textContent, /opportunities \| updated/);
    assert.equal(h.get('#refresh').disabled, false);
    assert.ok(h.get('#results').children.length > 0);
  }
});
test('quantity and profit respect budget, inventory and market depth', async () => {
  const h = harness(); await h.run('load()');
  const row = h.run('calculate(data[0])');
  assert.equal(row.units, 100); assert.equal(row.totalCost, 1000); assert.equal(row.totalProfit, 200);
  h.get('#available-coins').value = '100000'; h.get('#inventory-slots').value = '1';
  assert.equal(h.run('calculate(data[0]).units'), 64);
});
test('failed refresh removes old results and allows retry', async () => {
  const h = harness(); await h.run('load()');
  const original = h.context.fetch;
  h.context.fetch = async () => ({ ok: false, status: 503 });
  await h.run('load()');
  assert.match(h.get('#status').textContent, /HTTP 503/);
  assert.equal(h.get('#results').children.length, 0);
  assert.equal(h.run('data'), null); assert.equal(h.run('rawMarketData'), null);
  assert.equal(h.get('#refresh').disabled, false);
  h.context.fetch = original; await h.run('load()');
  assert.match(h.get('#status').textContent, /opportunities \| updated/);
});
test('stalled request aborts with an actionable error', async () => {
  const h = harness();
  h.context.fetch = (url, { signal }) => new Promise((resolve, reject) => signal.addEventListener('abort', () => reject(Error('aborted'))));
  await assert.rejects(h.run("fetchJson('fixture', 5)"), /timed out/);
});
test('malformed API data does not become a successful empty result', async () => {
  const h = harness(); h.context.fetch = async () => ({ ok: true, json: async () => ({ success: true }) });
  await h.run('load()'); assert.match(h.get('#status').textContent, /Could not load/);
  assert.equal(h.get('#refresh').disabled, false);
});
test('disabled browser storage does not prevent settings calculations', async () => {
  const h = harness('bazaar_to_npc', true); await h.run('load()');
  assert.doesNotThrow(() => h.run('saveSettings(); saveNpcDailyMarks(); render(data);'));
});
test('every relative HTML link and asset resolves in deployment folder', () => {
  for (const file of fs.readdirSync(docs).filter(f => f.endsWith('.html'))) {
    const html = fs.readFileSync(path.join(docs,file),'utf8');
    for (const [, ref] of html.matchAll(/(?:href|src)="([^"]+)"/g)) {
      if (/^(https?:|#|mailto:)/.test(ref)) continue;
      const target = path.resolve(docs, ref.split(/[?#]/)[0]);
      assert.ok(target.startsWith(docs), `${file}: link outside project: ${ref}`);
      assert.ok(fs.existsSync(target), `${file}: missing ${ref}`);
    }
    if (html.includes('data-route=')) {
      assert.ok(html.includes('./adsense_config.js'));
      assert.ok(html.includes('<noscript>'));
    }
  }
});
