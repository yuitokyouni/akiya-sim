#!/usr/bin/env python3
"""住調2023 第1-2表から空き家種類別（区市町村→6地域）を集計し ZONES_VAC を更新。"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "jyutaku_1-2_total.xlsx"
MAP_JSON = ROOT / "data" / "zone_municipality_map.json"
OUT_MUNI = ROOT / "data" / "muni_vac_types_jyutaku2023.csv"
OUT_ZONE = ROOT / "data" / "zones_vac_types_jyutaku2023.csv"
OUT_JS = ROOT / "data" / "zones_vac.gen.js"
OUT_DOC = ROOT / "docs/validation_vac_types_jyutaku2023.md"

STAT_INF = "000040209842"
SOURCE = "令和5年住宅・土地統計調査（2023年10月1日現在）"
TABLE = "第1-2表 居住世帯の有無(8区分)別住宅数（市区町村）"
ESTAT = f"https://www.e-stat.go.jp/stat-search/files?stat_infid={STAT_INF}"
ACQUIRED = date.today().isoformat()
ZONE_ORDER = ["西多摩", "多摩中部", "多摩東部", "区部西", "都心", "城東"]

EXCLUDED = {
    "大島町", "利島村", "新島村", "神津島村", "三宅村", "御蔵島村",
    "八丈町", "青ヶ島村", "小笠原村",
}


def zone_map() -> dict[str, str]:
    zones = json.loads(MAP_JSON.read_text(encoding="utf-8"))["zones"]
    m: dict[str, str] = {}
    for z, names in zones.items():
        for n in names:
            m[n] = z
    return m


def parse_rows() -> list[dict]:
    df = pd.read_excel(RAW, header=None)
    zm = zone_map()
    rows: list[dict] = []
    for i in range(9, len(df)):
        r = df.iloc[i]
        m = re.match(r"(\d+)_(.+)", str(r[1]).replace("　", " ").strip())
        if not m:
            continue
        code, name = m.group(1), m.group(2).strip()
        if not code.startswith("13") or code in ("13000", "13100"):
            continue
        if name in EXCLUDED:
            continue
        total = r[2]
        vacant = r[8]
        other = r[9]
        rent_v = r[10]
        sale_v = r[11]
        secondary = r[12]
        if pd.isna(total) or total in ("-", "nan"):
            continue
        total = int(total)
        vacant = 0 if pd.isna(vacant) or vacant in ("-", "nan") else int(vacant)
        other = 0 if pd.isna(other) or other in ("-", "nan") else int(other)
        rent_v = 0 if pd.isna(rent_v) or rent_v in ("-", "nan") else int(rent_v)
        sale_v = 0 if pd.isna(sale_v) or sale_v in ("-", "nan") else int(sale_v)
        secondary = 0 if pd.isna(secondary) or secondary in ("-", "nan") else int(secondary)
        if vacant <= 0:
            continue
        rows.append({
            "code": code,
            "name": name,
            "zone": zm.get(name, ""),
            "total": total,
            "vacant": vacant,
            "other_vacant": other,
            "rent_vacant": rent_v,
            "sale_vacant": sale_v,
            "secondary": secondary,
            "neg_frac": other / vacant,
            "list_frac": rent_v / vacant,
            "sale_frac": sale_v / vacant,
            "secondary_frac": secondary / vacant,
        })
    missing = [x["name"] for x in rows if not x["zone"]]
    if missing:
        raise SystemExit(f"Unmapped municipalities: {missing}")
    return rows


def aggregate(rows: list[dict]) -> dict[str, dict]:
    acc: dict[str, dict] = {z: defaultdict(float) for z in ZONE_ORDER}
    for row in rows:
        z = row["zone"]
        w = row["vacant"]
        acc[z]["vacant"] += row["vacant"]
        acc[z]["other"] += row["other_vacant"]
        acc[z]["rent"] += row["rent_vacant"]
        acc[z]["sale"] += row["sale_vacant"]
        acc[z]["secondary"] += row["secondary"]
        acc[z]["muni"] += 1
    out: dict[str, dict] = {}
    for z in ZONE_ORDER:
        a = acc[z]
        v = a["vacant"] or 1
        out[z] = {
            "vacant": int(a["vacant"]),
            "other_vacant": int(a["other"]),
            "rent_vacant": int(a["rent"]),
            "sale_vacant": int(a["sale"]),
            "secondary": int(a["secondary"]),
            "neg_frac": a["other"] / v,
            "list_frac": a["rent"] / v,
            "sale_frac": a["sale"] / v,
            "secondary_frac": a["secondary"] / v,
            "municipality_count": int(a["muni"]),
        }
    return out


def load_base_rates() -> list[float]:
    p = ROOT / "data" / "zones_vac_jyutaku2023.csv"
    rates: list[float] = []
    with p.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rates.append(float(row["vac_rate"]))
    return rates


def write_outputs(rows: list[dict], zones: dict[str, dict]) -> None:
    OUT_MUNI.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "code", "name", "zone", "total", "vacant",
        "other_vacant", "rent_vacant", "sale_vacant", "secondary",
        "neg_frac", "list_frac", "sale_frac", "secondary_frac",
        SOURCE, TABLE, ESTAT, ACQUIRED,
    ]
    with OUT_MUNI.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({**row, SOURCE: SOURCE, TABLE: TABLE, ESTAT: ESTAT, ACQUIRED: ACQUIRED})

    with OUT_ZONE.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "zone", "vacant", "other_vacant", "rent_vacant", "sale_vacant", "secondary",
            "neg_frac", "list_frac", "sale_frac", "secondary_frac", "municipality_count",
            "source_survey", "source_table", "source_estat", "acquired",
        ])
        for z in ZONE_ORDER:
            a = zones[z]
            w.writerow([
                z, a["vacant"], a["other_vacant"], a["rent_vacant"], a["sale_vacant"], a["secondary"],
                f"{a['neg_frac']:.6f}", f"{a['list_frac']:.6f}", f"{a['sale_frac']:.6f}",
                f"{a['secondary_frac']:.6f}", a["municipality_count"],
                SOURCE, TABLE, ESTAT, ACQUIRED,
            ])

    rates = load_base_rates()
    neg = [zones[z]["neg_frac"] for z in ZONE_ORDER]
    sale = [zones[z]["sale_frac"] for z in ZONE_ORDER]
    lst = [zones[z]["list_frac"] for z in ZONE_ORDER]
    OUT_JS.write_text(
        f"""/* AUTO-GENERATED by scripts/build_vac_types_jyutaku2023.py */
"use strict";
(function (root) {{
  root.ZONES_VAC = {{
    source: "{ESTAT}",
    survey: "{SOURCE}",
    table: "{TABLE}",
    rates: [{", ".join(f"{v:.6f}" for v in rates)}],
    negFrac: [{", ".join(f"{v:.4f}" for v in neg)}],
    saleFrac: [{", ".join(f"{v:.4f}" for v in sale)}],
    listFrac: [{", ".join(f"{v:.4f}" for v in lst)}],
    names: {json.dumps(ZONE_ORDER, ensure_ascii=False)},
    mapping: {{
      S_NEG: "住調:賃貸・売却用及び二次的住宅を除く空き家（その他）",
      S_LIST: "住調:賃貸用の空き家",
      S_SALE: "住調:売却用の空き家",
    }},
  }};
}})(typeof globalThis !== "undefined" ? globalThis : typeof self !== "undefined" ? self : this);
""",
        encoding="utf-8",
    )

    lines = [
        "# 住調2023 空き家種類別（t5）",
        "",
        "## 出典",
        f"- {SOURCE}",
        f"- {TABLE}",
        f"- [e-Stat]({ESTAT})",
        f"- 取得日: {ACQUIRED}",
        "",
        "## ABM 対応",
        "| 住調列 | ABM状態 |",
        "|--------|---------|",
        "| 221 その他空き家 | `S_NEG`（放置） |",
        "| 222 賃貸用 | `S_LIST` |",
        "| 223 売却用 | `S_SALE` |",
        "| 224 二次的住宅 | 現状 `S_NEG` に含めず集計のみ |",
        "",
        "## 6地域（空き家内シェア）",
        "",
        "| 地域 | 放置 | 賃貸用 | 売却用 | 二次的 |",
        "|------|------|--------|--------|--------|",
    ]
    for z in ZONE_ORDER:
        a = zones[z]
        lines.append(
            f"| {z} | {a['neg_frac']*100:.1f}% | {a['list_frac']*100:.1f}% | "
            f"{a['sale_frac']*100:.1f}% | {a['secondary_frac']*100:.1f}% |"
        )
    lines += ["", "## 再生成", "", "```bash", "python3 scripts/build_vac_types_jyutaku2023.py", "```", ""]
    OUT_DOC.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if not RAW.exists():
        raise SystemExit(f"Missing {RAW} — run build_zones_vac_jyutaku2023.py first or place e-Stat xlsx")
    rows = parse_rows()
    zones = aggregate(rows)
    write_outputs(rows, zones)
    print("zone,neg_frac,sale_frac,list_frac")
    for z in ZONE_ORDER:
        a = zones[z]
        print(f"{z},{a['neg_frac']:.4f},{a['sale_frac']:.4f},{a['list_frac']:.4f}")


if __name__ == "__main__":
    main()
