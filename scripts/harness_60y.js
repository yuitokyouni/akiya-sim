#!/usr/bin/env node
"use strict";
/**
 * Headless 60-year harness for akiya_abm_tokyo.html (HANDOFF §7).
 * Usage: node scripts/harness_60y.js [--seed=42] [--years=60]
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const htmlPath = path.join(__dirname, "..", "akiya_abm_tokyo.html");
const html = fs.readFileSync(htmlPath, "utf8");
const m = html.match(/<script>\s*([\s\S]*?)\s*<\/script>/);
if (!m) throw new Error("script block not found");

const seed = Number((process.argv.find((a) => a.startsWith("--seed=")) || "--seed=42").split("=")[1]);
const years = Number((process.argv.find((a) => a.startsWith("--years=")) || "--years=60").split("=")[1]);

let src = m[1];
// Drop browser-only UI wiring; keep simulation core.
const uiStart = src.indexOf("/* ---------- 描画 ---------- */");
if (uiStart >= 0) {
  src = src.slice(0, uiStart);
}
// const は vm サンドボックスの外から参照できないため var に置換
src = src.replace(/\bconst (ZONES|zone|N|W|H|S_OCC|S_RENT|S_SALE|S_LIST|S_NEG|S_DEMO|STATIONS|P)\b/g, "var $1");

const mockEl = () => ({
  value: "42",
  textContent: "",
  onclick: null,
  oninput: null,
  width: 960,
  height: 190,
  getContext: () => ({ clearRect() {}, fillRect() {}, beginPath() {}, moveTo() {}, lineTo() {}, stroke() {}, arc() {}, fillText() {} }),
});
const document = {
  getElementById: () => mockEl(),
};

const ctx = { console, Math, parseInt, parseFloat, document };
vm.createContext(ctx);
vm.runInContext(src, ctx);

function runWorld(policy) {
  const w = ctx.makeWorld(seed, policy);
  for (let y = 0; y < years; y++) ctx.step(w);
  return w;
}

function zoneVacRates(w) {
  const v = ctx.ZONES.map(() => 0);
  const t = ctx.ZONES.map(() => 0);
  for (let i = 0; i < ctx.N; i++) {
    const z = ctx.zone[i];
    if (z < 0 || w.st[i] === ctx.S_DEMO) continue;
    t[z]++;
    if (w.st[i] >= ctx.S_SALE && w.st[i] <= ctx.S_NEG) v[z]++;
  }
  return v.map((x, k) => (t[k] ? x / t[k] : 0));
}

const A = runWorld({ tax: 0, sub: 0 });
const L = A.hist.vac.length;
const vac = A.hist.vac[L - 1];
const neg = A.hist.neg[L - 1];
const clu = A.hist.clu[L - 1];
const zvac = zoneVacRates(A);

const out = {
  seed,
  years,
  baseline: { vac, neg, clu },
  zoneVac: Object.fromEntries(ctx.ZONES.map((Z, k) => [Z.n, zvac[k]])),
  zoneMig: Object.fromEntries(ctx.ZONES.map((Z) => [Z.n, Z.mig])),
};

console.log(JSON.stringify(out, null, 2));

// §3.4 gradient: 西多摩 > 多摩中部 > 多摩東部 > 区部西; 都心 is lowest; 城東 may exceed 都心
const rates = zvac;
const checks = [
  ["西多摩>多摩中部", rates[0] > rates[1]],
  ["多摩中部>多摩東部", rates[1] > rates[2]],
  ["多摩東部>区部西", rates[2] > rates[3]],
  ["区部西>都心", rates[3] > rates[4]],
  ["クラスタ>1", clu > 1],
];
let ok = true;
for (const [label, pass] of checks) {
  if (!pass) {
    console.error(`FAIL: ${label}`);
    ok = false;
  }
}
if (!ok) process.exit(1);
console.error("PASS: §3.4 regional gradient + cluster");
