import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const html = readFileSync('docs/index.html', 'utf8');
const section = (a, b) => { const start = html.indexOf(a); assert.ok(start >= 0, a); const end = html.indexOf(b, start); assert.ok(end > start, b); return html.slice(start, end); };
const nodes = new Map();
const node = () => ({ textContent: '', style: {}, classList: { add() {}, remove() {}, toggle() {} }, setAttribute() {}, querySelector() { return this; } });
const ctx = vm.createContext({ console, performance: { now: () => 10000 },
  $: id => { if (!nodes.has(id)) nodes.set(id, node()); return nodes.get(id); },
  play() {}, say() {}, floatAtCat() {}, queueSave() {}, setTimeout() {}, syncAlbumProgress() {},
  quizBank: () => [], prestigeReq: () => 2500,
  D: { levels: [[0, 'Начало'], [100, 'Друг'], [1000, 'Семья']], quizReward: 30, milestones: {} },
  S: { pets: 1000, totalPets: 1100, runPets: 1100, lives: 1, upg: {}, solved: 0 },
  LIFE_BONUS: .25, MAX_LIVES: 9, squash: { vel: 0 }, reduced: true,
});
const run = code => vm.runInContext(code, ctx);
run('let sleeping=false, zoomiesUntil=0, combo=0;');
run(section('function plural(n)', 'function say(text)'));
run(section('function fmt(n)', 'function addPets(gain, silent)'));
run(section('function refresh()', 'let lastT ='));
run(section('function syncAlbumProgress()', 'function openAlbum()'));
run(section('function updateShop()', 'function exportCode()'));
run(section('const PHOTOS =', 'if (S.photo &&'));
run(section('function addPets(gain, silent)', 'function floatText('));
run('refresh()');
const level = nodes.get('levelTitle').textContent;
const goal = nodes.get('photoGoal').textContent;
assert.match(goal, /Мышка поймана.*100 лапок/); // Массив фото не отсортирован по порогу.
run('buy(UPG.find(u=>u.id==="bowl"))');
assert.equal(run('S.pets'), 970);
assert.equal(run('S.totalPets'), 1100);
assert.equal(nodes.get('levelTitle').textContent, level);
assert.equal(nodes.get('photoGoal').textContent, goal);
for (const lives of [0, 1, 9]) {
  run(`S.lives=${lives}; S.upg={}; S.pets=1e9`);
  for (const id of ['click', 'bowl', 'scratch', 'fountain', 'clone', 'quiz', 'combo', 'zoom']) {
    run(`globalThis.u=UPG.find(u=>u.id==='${id}')`);
    const expected = run('upgradeValue(u, 1)');
    const before = run('upgradeValue(u, 0)');
    assert.ok(run('upgradeEffect(u, 0)').includes('→'));
    assert.ok(run('upgradeEffect(u, u.max)').includes('максимум'));
    const actual = () => run(id === 'click' ? 'clickPower()' : id === 'quiz' ? 'quizReward()' : id === 'combo' ? 'comboWindow()' : id === 'zoom' ? 'zoomMult()' : 'passiveRate()');
    const initial = actual();
    run('buy(u)');
    assert.ok(Math.abs((actual() - initial) - (expected - before)) < 1e-9, id);
  }
}
run('S.totalPets=290000; syncAlbumProgress()');
assert.match(nodes.get('photoGoal').textContent, /Все 31 фото открыты/);
// Реальный обработчик клика: серия добавляет к базе, оба множителя применяются затем.
run('let lastActivity=0,nextIdleQuiz=0,wakePoseUntil=0,lastPet=10,clicks=0,energy=0,zoomiesCooldownUntil=999,quiz=true;');
Object.assign(ctx, { initAudio() {}, tap() {}, spawnQuiz() {}, QUIZ_CADENCE: 26 });
run(section('function pet()', 'function mulberry32('));
for (const [series, boost, expected] of [[4, false, 2.5], [9, false, 3.75], [4, true, 12.5]]) {
  run(`S.lives=1; S.upg={}; S.pets=0; S.totalPets=1100; combo=${series}; zoomiesUntil=${boost ? 20 : 0}; lastPet=10; pet()`);
  assert.equal(run('S.pets'), expected);
}
assert.ok(!html.includes('Комбо x'));
console.log('PASS: lifetime level and photo goal survive purchases; nearest/all photos; all 8 upgrade previews match purchases at 0/1/9 lives; max states; series and boost rewards');
