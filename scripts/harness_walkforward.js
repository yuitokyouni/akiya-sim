#!/usr/bin/env node
"use strict";
/**
 * Walk-forward validation（大学受験過去問理論）
 *
 * 住調 wave t の地域別空き家率で初期化 → 5年シミュ → wave t+5 と突合。
 * パラメータは「未知の次波」を見て更新しない（本スクリプトは計測のみ）。
 *
 * Usage: node scripts/harness_walkforward.js [--seed=42] [--mae-max=0.05]
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.join(__dirname, "..");
const seed = Number((process.argv.find((a) => a.startsWith("--seed=")) || "--seed=42").split("=")[1]);
const maeMax = Number((process.argv.find((a) => a.startsWith("--mae-max=")) || "--mae-max=0.08").split("=")[1]);
const maeWarn = Number((process.argv.find((a) => a.startsWith("--mae-warn=")) || "--mae-warn=0.035").split("=")[1]);

const wavesPath = path.join(root, "data", "zones_vac_waves.json");
if (!fs.existsSync(wavesPath)) {
  console.error("Missing data/zones_vac_waves.json — run: python3 scripts/build_zones_vac_walkforward.py");
  process.exit(2);
}
const WAVES = JSON.parse(fs.readFileSync(wavesPath, "utf8"));

const ctx = { module: { exports: {} }, exports: {}, Int8Array };
ctx.globalThis = ctx;
const vmCtx = vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(root, "data", "zone_grid.gen.js"), "utf8"), vmCtx);
vm.runInContext(fs.readFileSync(path.join(root, "data", "zones_vac.gen.js"), "utf8"), vmCtx);
vm.runInContext(fs.readFileSync(path.join(root, "engine.js"), "utf8"), vmCtx);
const E = ctx.module.exports;

function setVacInit(rates) {
  const ZV = ctx.ZONES_VAC;
  ZV.rates = rates.slice();
  ZV.negFrac = WAVES.negFrac.slice();
  ZV.saleFrac = WAVES.saleFrac.slice();
  ZV.listFrac = WAVES.listFrac.slice();
}

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

function runHop(fromY, toY, years) {
  const from = WAVES.waves[String(fromY)];
  const to = WAVES.waves[String(toY)];
  if (!from || !to) throw new Error(`Missing wave ${fromY} or ${toY}`);

  setVacInit(from.rates);
  const w0 = E.makeWorld(seed, { tax: 0, sub: 0 });
  const initOverall = overallVac(w0);
  const initZone = zoneVacRates(w0);

  const w = E.makeWorld(seed, { tax: 0, sub: 0 });
  for (let y = 0; y < years; y++) E.step(w);
  const predOverall = overallVac(w);
  const predZone = zoneVacRates(w);

  const obsOverall = to.overall;
  const obsZone = to.rates;

  const zoneErr = predZone.map((p, k) => p - obsZone[k]);
  const mae =
    zoneErr.reduce((s, e) => s + Math.abs(e), 0) / zoneErr.length;
  const rmse = Math.sqrt(zoneErr.reduce((s, e) => s + e * e, 0) / zoneErr.length);

  return {
    hop: `${fromY}→${toY}`,
    years,
    init: {
      overall: initOverall,
      targetOverall: from.overall,
      zone: Object.fromEntries(E.ZONES.map((Z, k) => [Z.n, initZone[k]])),
      targetZone: Object.fromEntries(E.ZONES.map((Z, k) => [Z.n, from.rates[k]])),
    },
    predicted: {
      overall: predOverall,
      zone: Object.fromEntries(E.ZONES.map((Z, k) => [Z.n, predZone[k]])),
    },
    observed: {
      overall: obsOverall,
      zone: Object.fromEntries(E.ZONES.map((Z, k) => [Z.n, obsZone[k]])),
    },
    error: {
      overallPp: (predOverall - obsOverall) * 100,
      zonePp: Object.fromEntries(E.ZONES.map((Z, k) => [Z.n, zoneErr[k] * 100])),
      maePp: mae * 100,
      rmsePp: rmse * 100,
    },
  };
}

const hops = WAVES.hops.map((h) => runHop(h.from, h.to, h.years));
const meanMae = hops.reduce((s, h) => s + h.error.maePp, 0) / hops.length;

const out = {
  method: WAVES.method,
  nickname: WAVES.nickname,
  seed,
  note: "現行パラメータ固定の out-of-sample。答え（次波）を見てPをいじっていない。",
  hops,
  summary: {
    meanZoneMaePp: meanMae,
    hops: hops.map((h) => ({
      hop: h.hop,
      overallErrPp: h.error.overallPp,
      maePp: h.error.maePp,
    })),
  },
  gates: {
    maeWarnPp: maeWarn * 100,
    maeMaxPp: maeMax * 100,
  },
};

const reportPath = path.join(root, "docs", "validation_walkforward_latest.json");
fs.writeFileSync(reportPath, JSON.stringify(out, null, 2) + "\n");

console.log(JSON.stringify(out, null, 2));

let ok = true;
let warned = false;
for (const h of hops) {
  const initDrift = Math.abs(h.init.overall - h.init.targetOverall);
  if (initDrift > 0.015) {
    console.error(`FAIL: ${h.hop} t=0 init overall drift=${(initDrift * 100).toFixed(2)}pp`);
    ok = false;
  }
  if (h.error.maePp / 100 > maeMax) {
    console.error(
      `FAIL: ${h.hop} zone MAE=${h.error.maePp.toFixed(2)}pp > hard ${maeMax * 100}pp`
    );
    ok = false;
  } else if (h.error.maePp / 100 > maeWarn) {
    console.error(
      `WARN: ${h.hop} zone MAE=${h.error.maePp.toFixed(2)}pp > warn ${maeWarn * 100}pp（過去問のズレ＝補正候補）`
    );
    warned = true;
  }
}

if (!ok) {
  console.error("Walk-forward: FAIL. Report: docs/validation_walkforward_latest.json");
  process.exit(1);
}
console.error(
  `PASS: walk-forward ${hops.map((h) => h.hop).join(", ")} · mean MAE ${meanMae.toFixed(2)}pp` +
    (warned ? " （WARNあり＝次は学習区間だけでP補正）" : "")
);
console.error(`Report: ${reportPath}`);
