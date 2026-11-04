const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
function load(relative) {
  const exports = {};
  const code = ts.transpile(fs.readFileSync(path.join(__dirname, '..', relative), 'utf8'), {module:ts.ModuleKind.CommonJS});
  vm.runInNewContext(code, {exports, require});
  return exports;
}
const geo = load('src/utils/geo.ts');
const {resolveYRange} = load('src/utils/telemetry.ts');
test('fractional zoom keeps the center tile geography and scales tile size', () => {
  for (const zoom of [7, 7.05, 7.1, 7.9]) {
    const {tiles} = geo.getVisibleTiles(28.2333, -80.6, zoom, 1920, 1080);
    const center = tiles.find(t => t.drawX <= 960 && t.drawX + t.size > 960 && t.drawY <= 540 && t.drawY+t.size > 540);
    assert.equal(center.tileX, 35);
    assert.equal(center.tileY, 53);
    assert.ok(Math.abs(center.size - 256 * 2 ** (zoom - Math.floor(zoom))) < 1e-8);
  }
});
test('threshold and line use one autoscale range', () => {
  assert.deepEqual(Array.from(resolveYRange([0,100])), [-15,115]);
  assert.deepEqual(Array.from(resolveYRange([0,100], [-20,120])), [-20,120]);
});
