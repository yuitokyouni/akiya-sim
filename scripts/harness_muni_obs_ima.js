#!/usr/bin/env node
"use strict";
/**
 * Gate for citizen「いま」card: municipality facts must be real observations.
 * Usage: node scripts/harness_muni_obs_ima.js
 */
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const p = path.join(root, "data", "muni_obs_ima.json");
if (!fs.existsSync(p)) {
  console.error("Missing data/muni_obs_ima.json — run: python3 scripts/build_muni_obs_ima.py");
  process.exit(2);
}
const data = JSON.parse(fs.readFileSync(p, "utf8"));
const munis = data.municipalities || [];

let ok = true;
const checks = [];

function check(label, pass) {
  checks.push([label, pass]);
  if (!pass) {
    console.error("FAIL: " + label);
    ok = false;
  }
}

check("対象が40以上の市区町村", munis.length >= 40);
check("空き家率が全件埋まる", munis.every((m) => typeof m.vac_rate === "number"));
check("高齢化率がほぼ全件", munis.filter((m) => m.aging_rate != null).length >= munis.length - 2);
check("人口がほぼ全件", munis.filter((m) => m.pop != null).length >= munis.length - 2);
check("自然増減がほぼ全件", munis.filter((m) => m.natural != null).length >= munis.length - 2);

const chiyoda = munis.find((m) => m.name === "千代田区");
check("千代田区がある", !!chiyoda);
if (chiyoda) {
  check("千代田区 vac が 5–25%", chiyoda.vac_rate > 0.05 && chiyoda.vac_rate < 0.25);
  check("千代田区 aging が 5–40%", chiyoda.aging_rate > 0.05 && chiyoda.aging_rate < 0.4);
}

// Search aliases resolve
const stations = data.stations || [];
check("駅エイリアスが8件以上", stations.length >= 8);
for (const s of stations) {
  const hit = munis.find((m) => m.name === s.muni);
  check(`駅「${s.name}」→ ${s.muni} が観測パックにある`, !!hit);
}

// No ranking field leaking
check("ランキング用フィールドを持たない", !("rank" in (munis[0] || {})));

const report = {
  status: ok ? "PASS" : "FAIL",
  coverage: data.coverage,
  sample: chiyoda
    ? {
        name: chiyoda.name,
        copy_vac: chiyoda.copy_vac,
        copy_aging: chiyoda.copy_aging,
        copy_pop: chiyoda.copy_pop,
      }
    : null,
};
console.log(JSON.stringify(report, null, 2));
if (!ok) process.exit(1);
console.error(
  `PASS: muni「いま」観測パック ${munis.length}件 · vac/age/pop 充足 · 駅エイリアス ${stations.length}`
);
