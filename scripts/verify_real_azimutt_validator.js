const fs = require('fs');
const vm = require('vm');
const path = require('path');

process.on('unhandledRejection', () => {});

// 1. Setup Sandbox to run Azimutt bundle in Node
const scriptPath = 'C:/Users/basti/.gemini/antigravity-cli/brain/ec9598a2-ab2e-4a93-ba07-bd83020546a9/scratch/azimutt_script.js';
let bundleContent = fs.readFileSync(scriptPath, 'utf8');

// Expose models export function `ere` from the bundle IIFE
bundleContent = bundleContent.replace('Kge();})();', 'globalThis.ere = ere; Kge();})();');

const sandbox = {
  console: { log: () => {}, error: () => {}, warn: () => {}, info: () => {}, debug: () => {} },
  setTimeout, clearTimeout, setInterval, clearInterval,
  Date, Math, JSON, Array, Object, RegExp, String, Number, Boolean, Error, TypeError, Promise,
  fetch: globalThis.fetch, Request: globalThis.Request, Response: globalThis.Response, Headers: globalThis.Headers,
  FormData: globalThis.FormData, Blob: globalThis.Blob, File: globalThis.File, ReadableStream: globalThis.ReadableStream,
  TextEncoder: globalThis.TextEncoder, TextDecoder: globalThis.TextDecoder,
  ResizeObserver: class { observe() {} unobserve() {} disconnect() {} },
  window: {},
  document: {
    getElementById: () => null, maybeElementById: () => [],
    addEventListener: () => {}, removeEventListener: () => {},
    querySelector: () => null, getElementsByTagName: () => [{ setAttribute: () => {} }],
    body: { appendChild: () => {}, removeChild: () => {} }
  },
  navigator: { userAgent: 'node' },
  location: { href: 'http://localhost/', pathname: '/', search: '', hash: '' },
  crypto: { randomUUID: () => '00000000-0000-0000-0000-000000000000' },
  addEventListener: () => {}, removeEventListener: () => {},
  Elm: { Main: { init: () => ({ ports: { elmToJs: { subscribe: () => {} }, jsToElm: { send: () => {} } } }) } }
};
sandbox.window = sandbox;
sandbox.self = sandbox;
sandbox.globalThis = sandbox;

vm.createContext(sandbox);
vm.runInContext(bundleContent, sandbox);
const models = sandbox.ere();

console.log('='.repeat(80));
console.log('AZIMUTT OFFICIAL VALIDATOR EXECUTION REPORT');
console.log('='.repeat(80));

// ==========================================
// Test 1: Union kind check on sources[0].kind
// ==========================================
console.log('\n--- 1. sources[0].kind Schema & Value Validation ---');
const currentFile = JSON.parse(fs.readFileSync('sources/bank_raya.azimutt.json', 'utf8'));
const currentKind = currentFile.sources[0].kind;
console.log('sources[0].kind value:');
console.log(JSON.stringify(currentKind, null, 2));

const kindValidation = models.LegacySourceKind.safeParse(currentKind);
console.log('LegacySourceKind.safeParse(sources[0].kind):', kindValidation.success ? 'PASSED (VALID)' : 'FAILED');
if (!kindValidation.success) {
  console.log('Errors:', JSON.stringify(kindValidation.error.issues, null, 2));
}

// ==========================================
// Test 2: Negative Test on Old File Structure
// ==========================================
console.log('\n--- 2. Negative Test (Old File Structure) ---');
// Reproducing old structure: missing _type: "json", containing id, createdAt, updatedAt, and types with "values"
const oldFile = JSON.parse(JSON.stringify(currentFile));
delete oldFile._type;
oldFile.id = '00000000-0000-4000-8000-000000000001';
oldFile.createdAt = 1729900000000;
oldFile.updatedAt = 1729900000000;
oldFile.sources[0].types = [{
  schema: 'datamart',
  name: 'scoring_details',
  values: ['model_version STRING', 'probability_of_default NUMERIC', 'score_cutoff INT64']
}];

const negResult = models.LegacyProjectJson.safeParse(oldFile);
console.log('LegacyProjectJson.safeParse(oldFile) success:', negResult.success);
if (!negResult.success) {
  console.log(`ZodError detected as expected (${negResult.error.issues.length} issue(s)):`);
  negResult.error.issues.forEach((issue, idx) => {
    console.log(`  Issue ${idx + 1}: [${issue.code}] at '${issue.path.join('.') || 'root'}': ${issue.message}`);
  });
}

// ==========================================
// Test 3: Positive Test on New File Structure
// ==========================================
console.log('\n--- 3. Positive Test (New Regenerated File) ---');
const newFile = JSON.parse(fs.readFileSync('sources/bank_raya.azimutt.json', 'utf8'));
const posResult = models.LegacyProjectJson.safeParse(newFile);
console.log('LegacyProjectJson.safeParse(newFile) success:', posResult.success);
if (posResult.success) {
  console.log('PASSED! Regenerated bank_raya.azimutt.json 100% conforms to LegacyProjectJson.');
} else {
  console.log('FAILED! Issues:', JSON.stringify(posResult.error.issues, null, 2));
}

// ==========================================
// Test 4: Layout Columns and Position Checks
// ==========================================
console.log('\n--- 4. Layout Columns & Position Checks ---');
const sourceTables = {};
newFile.sources[0].tables.forEach(t => {
  const fullId = (t.schema ? t.schema + '.' : '') + (t.table || t.name);
  sourceTables[fullId] = new Set(t.columns.map(c => c.name));
});

let layoutColErrors = 0;
let layoutPosErrors = 0;
const layoutCount = Object.keys(newFile.layouts).length;

for (const [lName, layout] of Object.entries(newFile.layouts)) {
  const seenPos = new Map();
  for (const tbl of layout.tables) {
    // Column check
    const validCols = sourceTables[tbl.id];
    if (!validCols) {
      console.log(`  [${lName}] Table ${tbl.id} not found in source!`);
      layoutColErrors++;
    } else {
      for (const col of tbl.columns) {
        if (!validCols.has(col)) {
          console.log(`  [${lName}] Table ${tbl.id} col ${col} not in table schema!`);
          layoutColErrors++;
        }
      }
    }
    // Position check
    const posKey = `${tbl.position.left},${tbl.position.top}`;
    if (seenPos.has(posKey)) {
      console.log(`  [${lName}] Duplicate position ${posKey} between ${seenPos.get(posKey)} and ${tbl.id}!`);
      layoutPosErrors++;
    } else {
      seenPos.set(posKey, tbl.id);
    }
  }
}

console.log(`Total Layouts Evaluated: ${layoutCount}`);
console.log(`Column Inconsistencies: ${layoutColErrors}`);
console.log(`Duplicate Table Coordinates: ${layoutPosErrors}`);
if (layoutColErrors === 0 && layoutPosErrors === 0) {
  console.log('PASSED! All layout columns exist in tables, and all positions are distinct within each layout.');
}

console.log('='.repeat(80));
process.exit(0);
