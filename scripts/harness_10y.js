#!/usr/bin/env node
"use strict";
/**
 * Primary validation gate: 住調2023-calibrated init + 0–10y short-term drift.
 * Usage: node scripts/harness_10y.js [--seed=42]
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.join(__dirname, "..");
const ctx = { module: { exports: {} }, exports: {}, Int8Array };
ctx.globalThis = ctx;
const vmCtx = vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(root, "data", "zone_grid.gen.js"), "utf8"), vmCtx);
vm.runInContext(fs.readFileSync(path.join(root, "data", "zones_vac.gen.js"), "utf8"), vmCtx);
vm.runInContext(fs.readFileSync(path.join(root, "engine.js"), "utf8"), vmCtx);
const E = ctx.module.exports;

const seed = Number((process.argv.find((a) => a.startsWith("--seed=")) || "--seed=42").split("=")[1]);
const ZV = ctx.ZONES_VAC;

function overallVac(w) {
  let tot = 0;
  let vac = 0;
  for (let i = 0; i < E.N; i++) {
    if (E.zone[i] < 0 || w.st[i] === E.S_DEMO) continue;
    tot++;
    if (w.st[i] >= E.S_SALE && w.st[i] <= E.S_NEG) vac++;
  }
  return tot ? vac / tot : 0;
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

function runYears(years) {
  const w = E.makeWorld(seed, { tax: 0, sub: 0 });
  for (let y = 0; y < years; y++) E.step(w);
  return w;
}

const w0 = runYears(0);
const w10 = runYears(10);
const vac0 = overallVac(w0);
const vac10 = overallVac(w10);
const z0 = zoneVacRates(w0);
const z10 = zoneVacRates(w10);

function expectedOverallVac() {
  const counts = E.ZONES.map(() => 0);
  for (let i = 0; i < E.N; i++) {
    const z = E.zone[i];
    if (z >= 0) counts[z]++;
  }
  const tot = counts.reduce((a, b) => a + b, 0);
  return counts.reduce((s, c, k) => s + c * ZV.rates[k], 0) / tot;
}
const target0 = expectedOverallVac();
const out = {
  seed,
  source: ZV.source,
  survey: ZV.survey,
  t0: { overall: vac0, zone: Object.fromEntries(E.ZONES.map((Z, k) => [Z.n, z0[k]])) },
  t10: { overall: vac10, zone: Object.fromEntries(E.ZONES.map((Z, k) => [Z.n, z10[k]])) },
  targets: {
    t0Zone: Object.fromEntries(E.ZONES.map((Z, k) => [Z.n, ZV.rates[k]])),
    t10OverallBand: [0.10, 0.18],
  },
};

console.log(JSON.stringify(out, null, 2));

let ok = true;
const ZONE_TOL = 0.012; // ±1.2pp at t=0 (rounding in stratified init)
for (let k = 0; k < E.ZONES.length; k++) {
  const diff = Math.abs(z0[k] - ZV.rates[k]);
  if (diff > ZONE_TOL) {
    console.error(`FAIL: t=0 ${E.ZONES[k].n} vac=${z0[k].toFixed(4)} target=${ZV.rates[k].toFixed(4)} (|Δ|=${diff.toFixed(4)})`);
    ok = false;
  }
}
if (Math.abs(vac0 - target0) > 0.005) {
  console.error(`FAIL: t=0 overall vac=${vac0.toFixed(4)} expected≈${target0.toFixed(4)}`);
  ok = false;
}
const [lo, hi] = out.targets.t10OverallBand;
if (vac10 < lo || vac10 > hi) {
  console.error(`FAIL: t=10 overall vac=${vac10.toFixed(4)} outside band [${lo}, ${hi}]`);
  ok = false;
}

if (!ok) process.exit(1);
console.error(`PASS: 住調2023 init (t=0 zone ±${(ZONE_TOL * 100).toFixed(1)}pp) + t=10 overall ${(vac10 * 100).toFixed(2)}% in [${lo * 100}%, ${hi * 100}%]`);
