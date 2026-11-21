import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const html = readFileSync('docs/index.html', 'utf8');
for (const [, script] of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)) new vm.Script(script);
const section = (a, b) => html.slice(html.indexOf(a), html.indexOf(b, html.indexOf(a)));
function game(reduced = false) {
  const nodes = new Map();
  const ctx = vm.createContext({ reduced, console, performance: { now: () => 100000 },
    $: id => { if (!nodes.has(id)) nodes.set(id, { textContent: '', classList: { toggle() {} } }); return nodes.get(id); },
    say() {}, play() {}, zoomMult: () => 5,
    hideQuiz() {}, S: { pets: 42 }, ZOOMIES_SECONDS: 6, ZOOMIES_COOLDOWN: 35 });
  vm.runInContext('let energy=0, zoomiesUntil=0, zoomiesCooldownUntil=0, combo=0, clicks=0, shownScore=0, sleeping=false, lastPet=0, wakePoseUntil=0, lastActivity=0, nextIdleQuiz=0, quizOrderCache=null; const squash={v:1,vel:1};', ctx);
  vm.runInContext(section('function updateZoomies(now)', 'function pet()'), ctx);
  vm.runInContext(section('function resetTransients()', 'function switchStudent('), ctx);
  return code => vm.runInContext(code, ctx);
}
for (const reduced of [false, true]) {
  const run = game(reduced);
  run('energy=99.9; updateZoomies(10)');
  assert.equal(run('zoomiesUntil'), 0);
  run('energy=100; updateZoomies(10)');
  assert.equal(run('zoomiesUntil'), 16);
  assert.equal(run('zoomiesCooldownUntil'), 51);
  run('updateZoomies(13)'); assert.equal(run('energy'), 50);
  run('updateZoomies(16)'); assert.equal(run('energy'), 0);
  run('energy=100; updateZoomies(30)'); assert.equal(run('zoomiesUntil'), 0);
  assert.match(run('$("energyStatus").textContent'), /старт автоматически/);
  run('updateZoomies(51)'); assert.equal(run('zoomiesUntil'), 57);
  run('resetTransients()');
  assert.equal(run('zoomiesUntil + zoomiesCooldownUntil + energy'), 0);
  assert.equal(run('lastActivity'), 100);
}
// Обработчик pet из приложения, подменены только звук, DOM и начисление счёта.
const ctx = vm.createContext({ performance: { now: () => 10000 }, S: { bestCombo: 0 },
  lvl: () => 0, seriesBonus: n => n >= 10 ? 2 : n >= 5 ? 1 : 0, lifeMult: () => 1, zoomMult: () => 5, addPets: () => false,
  initAudio() {}, say() {}, play() {}, floatAtCat() {}, fmt: String, tap() {},
  refresh() {}, queueSave() {}, spawnQuiz() {}, comboWindow: () => 1.4,
  QUIZ_CADENCE: 26, ZOOMIES_SECONDS: 6, ZOOMIES_COOLDOWN: 35 });
vm.runInContext('let energy=0, zoomiesUntil=0, zoomiesCooldownUntil=0, combo=0, lastPet=-99, lastActivity=0, nextIdleQuiz=0, sleeping=false, wakePoseUntil=0, clicks=0, quiz=null; const squash={vel:0};', ctx);
vm.runInContext(section('function startZoomies(now)', 'function mulberry32('), ctx);
vm.runInContext('for(let i=0;i<49;i++) pet()', ctx);
assert.equal(vm.runInContext('energy', ctx), 98);
assert.equal(vm.runInContext('zoomiesUntil', ctx), 0);
vm.runInContext('pet()', ctx);
assert.equal(vm.runInContext('zoomiesUntil', ctx), 16);
vm.runInContext('pet()', ctx);
assert.equal(vm.runInContext('zoomiesUntil', ctx), 16);
assert.ok(!section('function tick(t)', '$("catWrap").addEventListener').includes('energy - dt'));
assert.ok(html.includes('if (now >= zoomiesUntil) energy = Math.min(100, energy + 2)'));
console.log('PASS: inline JavaScript syntax; charge threshold; boost duration; queued cooldown; reduced-motion parity; transient reset');
