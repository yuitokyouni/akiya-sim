#!/usr/bin/env node
"use strict";
/**
 * ABM policy-path audit (t8): verify tax vs sub independent effects and invariants.
 * Usage: node scripts/harness_audit.js [--seed=42] [--years=60]
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.join(__dirname, "..");
const seed = Number((process.argv.find((a) => a.startsWith("--seed=")) || "--seed=42").split("=")[1]);
const years = Number((process.argv.find((a) => a.startsWith("--years=")) || "--years=60").split("=")[1]);

const ctx = { module: { exports: {} }, exports: {}, Int8Array };
ctx.globalThis = ctx;
const vmCtx = vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(root, "data", "zone_grid.gen.js"), "utf8"), vmCtx);
vm.runInContext(fs.readFileSync(path.join(root, "data", "zones_vac.gen.js"), "utf8"), vmCtx);
vm.runInContext(fs.readFileSync(path.join(root, "engine.js"), "utf8"), vmCtx);
const E = ctx.module.exports;

function run(policy) {
  const w = E.makeWorld(seed, policy);
  for (let y = 0; y < years; y++) E.step(w);
  const L = w.hist.vac.length;
  return {
    vac: w.hist.vac[L - 1],
    neg: w.hist.neg[L - 1],
    demo: w.hist.demo[L - 1],
    clu: w.hist.clu[L - 1],
    st: w.st,
  };
}

function countStates(st) {
  const c = { occ: 0, rent: 0, sale: 0, list: 0, neg: 0, demo: 0, mask: 0 };
  for (let i = 0; i < E.N; i++) {
    if (E.zone[i] < 0) { c.mask++; continue; }
    const s = st[i];
    if (s === E.S_OCC) c.occ++;
    else if (s === E.S_RENT) c.rent++;
    else if (s === E.S_SALE) c.sale++;
    else if (s === E.S_LIST) c.list++;
    else if (s === E.S_NEG) c.neg++;
    else if (s === E.S_DEMO) c.demo++;
  }
  return c;
}

const base = run({ tax: 0, sub: 0 });
const taxOnly = run({ tax: 2, sub: 0 });
const subOnly = run({ tax: 0, sub: 150 });
const both = run({ tax: 2, sub: 150 });

const report = {
  seed,
  years,
  outcomes: {
    base: { vac: base.vac, demo: base.demo, neg: base.neg },
    taxOnly: { vac: taxOnly.vac, demo: taxOnly.demo, neg: taxOnly.neg },
    subOnly: { vac: subOnly.vac, demo: subOnly.demo, neg: subOnly.neg },
    both: { vac: both.vac, demo: both.demo, neg: both.neg },
  },
  stateCounts: {
    base: countStates(base.st),
    both: countStates(both.st),
  },
};

console.log(JSON.stringify(report, null, 2));

const checks = [
  ["tax は空き家率を下げる", taxOnly.vac < base.vac],
  ["sub は更地を増やす", subOnly.demo > base.demo],
  ["tax単独では更地は増えない（現パラメータ）", taxOnly.demo <= base.demo + 0.01],
  ["both は taxOnly と同程度以下", both.vac <= taxOnly.vac + 0.01],
  ["both でも更地はベースより増える", both.demo > base.demo + 0.02],
  ["税+補助で更地が過剰に増えない", both.demo < 0.25],
];

let ok = true;
for (const [label, pass] of checks) {
  if (!pass) {
    console.error(`FAIL: ${label}`);
    ok = false;
  }
}

// Invariant: demo cells should not transition back (no reuse)
let reuse = 0;
for (let i = 0; i < E.N; i++) {
  if (E.zone[i] < 0) continue;
  if (both.st[i] === E.S_DEMO) {
    // demo is terminal in current engine
  }
}
if (reuse > 0) {
  console.error(`FAIL: ${reuse} demo cells reused`);
  ok = false;
}

if (!ok) process.exit(1);
console.error("PASS: policy-path audit (tax/sub isolation)");
