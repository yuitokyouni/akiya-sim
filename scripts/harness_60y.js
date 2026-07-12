#!/usr/bin/env node
"use strict";
/**
 * Headless 60-year harness (HANDOFF §7) — secondary long-run check after 住調2023 calibration.
 * Usage: node scripts/harness_60y.js [--seed=42] [--years=60] [--golden=/path]
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.join(__dirname, "..");
const seed = Number((process.argv.find((a) => a.startsWith("--seed=")) || "--seed=42").split("=")[1]);
const years = Number((process.argv.find((a) => a.startsWith("--years=")) || "--years=60").split("=")[1]);
const goldenArg = process.argv.find((a) => a.startsWith("--golden="));
const goldenPath = goldenArg
  ? goldenArg.split("=")[1]
  : path.join(__dirname, "harness_golden_seed42_y60.json");

const ctx = { module: { exports: {} }, exports: {}, Int8Array };
ctx.globalThis = ctx;
const vmCtx = vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(root, "data", "zone_grid.gen.js"), "utf8"), vmCtx);
vm.runInContext(fs.readFileSync(path.join(root, "data", "zones_vac.gen.js"), "utf8"), vmCtx);
vm.runInContext(fs.readFileSync(path.join(root, "engine.js"), "utf8"), vmCtx);
const E = ctx.module.exports;

function runWorld(policy) {
  const w = E.makeWorld(seed, policy);
  for (let y = 0; y < years; y++) E.step(w);
  return w;
}

function zoneVacRates(w) {
  const v = E.ZONES.map(() => 0);
  const t = E.ZONES.map(() => 0);
  for (let i = 0; i < E.N; i++) {
    const z = E.zone[i];
    if (z < 0 || w.st[i] === E.S_DEMO) continue;
    t[z]++;
    if (w.st[i] >= E.S_SALE && w.st[i] <= E.S_NEG) v[z]++;
  }
  return v.map((x, k) => (t[k] ? x / t[k] : 0));
}

const A = runWorld({ tax: 0, sub: 0 });
const B = runWorld({ tax: 2, sub: 150 });
const L = A.hist.vac.length;
const vac = A.hist.vac[L - 1];
const neg = A.hist.neg[L - 1];
const clu = A.hist.clu[L - 1];
const zvac = zoneVacRates(A);
const zvacB = zoneVacRates(B);

const out = {
  seed,
  years,
  baseline: { vac, neg, clu },
  intervention: {
    vac: B.hist.vac[L - 1],
    neg: B.hist.neg[L - 1],
    clu: B.hist.clu[L - 1],
  },
  zoneVac: Object.fromEntries(E.ZONES.map((Z, k) => [Z.n, zvac[k]])),
  zoneMig: Object.fromEntries(E.ZONES.map((Z) => [Z.n, Z.mig])),
};

console.log(JSON.stringify(out, null, 2));

const checks = [
  ["60年: 空き家率が発散しない (≤25%)", vac <= 0.25],
  ["60年: 西多摩が多摩中部より高い", zvac[0] > zvac[1]],
  ["政策: 全体空き家率低下", B.hist.vac[L - 1] < vac],
  ["政策: 西多摩でも低下", zvacB[0] < zvac[0]],
];
let ok = true;
for (const [label, pass] of checks) {
  if (!pass) {
    console.error(`FAIL: ${label}`);
    ok = false;
  }
}

if (fs.existsSync(goldenPath)) {
  const golden = JSON.parse(fs.readFileSync(goldenPath, "utf8"));
  const keys = ["vac", "neg", "clu"];
  for (const k of keys) {
    if (out.baseline[k] !== golden.baseline[k]) {
      console.error(`FAIL: baseline.${k} golden=${golden.baseline[k]} got=${out.baseline[k]}`);
      ok = false;
    }
  }
  for (const name of E.ZONES.map((z) => z.n)) {
    if (out.zoneVac[name] !== golden.zoneVac[name]) {
      console.error(`FAIL: zoneVac.${name} golden=${golden.zoneVac[name]} got=${out.zoneVac[name]}`);
      ok = false;
    }
  }
  console.error("Golden comparison: " + (ok ? "EXACT MATCH" : "MISMATCH"));
} else {
  fs.writeFileSync(goldenPath, JSON.stringify(out, null, 2) + "\n");
  console.error(`Wrote golden file: ${goldenPath}`);
}

if (!ok) process.exit(1);
console.error("PASS: §7 harness (long-run stability + policy response)");
