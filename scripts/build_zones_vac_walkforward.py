#!/usr/bin/env python3
"""Build multi-wave 住調 vacancy rates for walk-forward (大学受験過去問) validation.

Waves: 2008 / 2013 / 2018 / 2023 → 6 ABM zones.
Usage: python3 scripts/build_zones_vac_walkforward.py
"""

from __future__ import annotations

import json
import re
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MAP_JSON = ROOT / "data" / "zone_municipality_map.json"
OUT_JSON = ROOT / "data" / "zones_vac_waves.json"
OUT_CSV = ROOT / "data" / "zones_vac_waves.csv"
OUT_JS = ROOT / "data" / "zones_vac_waves.gen.js"

ZONE_ORDER = ["西多摩", "多摩中部", "多摩東部", "区部西", "都心", "城東"]
EXCLUDED = {
    "大島町", "利島村", "新島村", "神津島村", "三宅村", "御蔵島村",
    "八丈町", "青ヶ島村", "小笠原村",
}

# e-Stat file downloads (居住世帯の有無 → 空き家)
WAVES = {
    2008: {
        "label": "平成20年住宅・土地統計調査（2008年10月1日現在）",
        "statInfId": "000007370942",
        "table": "居住世帯の有無(8区分)別住宅数―市区町村（東京都）",
        "file": RAW / "jyutaku2008_tokyo_1-2.xlsx",
        "parser": "tokyo_pref_xls",
    },
    2013: {
        "label": "平成25年住宅・土地統計調査（2013年10月1日現在）",
        "statInfId": "000028111878",
        "table": "居住世帯の有無(8区分)別住宅数―市区町村（東京都）",
        "file": RAW / "jyutaku2013_tokyo_1-2.xlsx",
        "parser": "tokyo_pref_xls",
    },
    2018: {
        "label": "平成30年住宅・土地統計調査（2018年10月1日現在）",
        "statInfId": "000031865669",
        "table": "第1-2表 居住世帯の有無(8区分)別住宅数（全国・都道府県・市区町村）",
        "file": RAW / "jyutaku2018_1-2.xlsx",
        "parser": "national_1_2",
    },
    2023: {
        "label": "令和5年住宅・土地統計調査（2023年10月1日現在）",
        "statInfId": "000040209842",
        "table": "第1-2表 居住世帯の有無(8区分)別住宅数（市区町村）",
        "file": RAW / "jyutaku_1-2_total.xlsx",
        "parser": "national_1_2",
    },
}


def load_zone_map() -> dict[str, str]:
    zones = json.loads(MAP_JSON.read_text(encoding="utf-8"))["zones"]
    m: dict[str, str] = {}
    for z, names in zones.items():
        for n in names:
            m[n] = z
    return m


def clean_muni_name(raw: str) -> str:
    s = str(raw)
    s = re.sub(r"^\d+\s*", "", s)  # leading codes like 101
    s = s.replace("\u3000", "").replace(" ", "").replace("　", "")
    s = s.strip()
    # "千代田区" after stripping spaces from "千 代 田 区"
    return s


def ensure_file(meta: dict) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    path: Path = meta["file"]
    if path.exists() and path.stat().st_size > 1000:
        return
    url = f"https://www.e-stat.go.jp/stat-search/file-download?statInfId={meta['statInfId']}&fileKind=0"
    print(f"Downloading {meta['statInfId']} -> {path.name}")
    urllib.request.urlretrieve(url, path)


def parse_tokyo_pref_xls(path: Path) -> list[dict]:
    """2008/2013 Tokyo-volume Excel: spaced JP names, vacant at fixed columns."""
    df = pd.read_excel(path, header=None)
    rows: list[dict] = []
    for i in range(16, len(df)):
        name_raw = df.iloc[i, 7]
        if pd.isna(name_raw):
            continue
        name = clean_muni_name(name_raw)
        if not name or name in ("特別区部", "市部", "町村部") or "計" in name:
            continue
        if name in EXCLUDED:
            continue
        # Prefer names ending with 区/市/町/村
        if not re.search(r"(区|市|町|村)$", name):
            continue
        total = df.iloc[i, 9]
        vacant = df.iloc[i, 15]
        if total in ("-", "", None) or pd.isna(total):
            continue
        total = int(float(total))
        vacant = 0 if vacant in ("-", "", None) or pd.isna(vacant) else int(float(vacant))
        if total <= 0:
            continue
        rows.append({"code": "", "name": name, "total": total, "vacant": vacant, "vac_rate": vacant / total})
    return rows


def parse_national_1_2(path: Path) -> list[dict]:
    """2018/2023 nationwide municipality table — Tokyo only."""
    df = pd.read_excel(path, header=None)
    # Detect layout: 2023 has region in col1 and vacancy in col8; 2018 has region in col5, total col6, vacant col12
    header_row = None
    for i in range(min(15, len(df))):
        vals = [str(x) for x in df.iloc[i].tolist()]
        if any("空き家" in v for v in vals) and any("総数" in v or "0_総数" in v for v in vals):
            header_row = i
            break
    if header_row is None:
        raise SystemExit(f"Cannot find vacancy header in {path}")

    headers = [str(x) for x in df.iloc[header_row].tolist()]
    # Find total / vacant column indices
    total_col = vacant_col = region_col = None
    for j, h in enumerate(headers):
        if h in ("0_総数",) or h.strip() == "0_総数":
            total_col = j
        if "22_空き家" in h or h.strip() == "22_空き家":
            vacant_col = j
    # 2018 multi-row header: columns already known if nan-heavy header row
    if total_col is None or vacant_col is None:
        # Probe first Tokyo row style
        # 2018: col4=idcode, col5=region, col6=total, col12=vacant
        for i in range(header_row + 1, min(header_row + 30, len(df))):
            for j in range(min(8, df.shape[1])):
                v = str(df.iloc[i, j])
                if "13000_東京都" in v or "13101_" in v:
                    region_col = j
                    break
            if region_col is not None:
                break
        if region_col is None:
            # 2023 style: region in col1
            region_col = 1
            total_col = 2
            vacant_col = 8
        else:
            total_col = region_col + 1
            # vacant is typically 6 columns after total in 2018 file (22_空き家)
            vacant_col = region_col + 7  # 5→12
    else:
        region_col = 1 if str(df.iloc[header_row + 1, 1]).startswith(("0", "1")) or "_" in str(df.iloc[header_row + 1, 1]) else 5
        # Prefer col that has 地域
        for j in range(min(6, df.shape[1])):
            sample = str(df.iloc[header_row + 1, j])
            if re.match(r"\d{5}_", sample) or sample.startswith("00000_"):
                region_col = j
                break

    # Refine 2018 vs 2023 by spotting column layout from a known row
    rows: list[dict] = []
    for i in range(header_row + 1, len(df)):
        # Try both common region columns
        region = None
        for j in (1, 5):
            if j >= df.shape[1]:
                continue
            v = str(df.iloc[i, j])
            if re.match(r"13\d{3}_", v):
                region = v
                region_col = j
                break
        if region is None:
            continue
        m = re.match(r"(\d+)_(.+)", region.replace("　", " ").strip())
        if not m:
            continue
        code, name = m.group(1), m.group(2).strip().replace(" ", "")
        if not code.startswith("13") or code in ("13000", "13100"):
            continue
        if name in EXCLUDED:
            continue
        if region_col == 5:
            total = df.iloc[i, 6]
            vacant = df.iloc[i, 12]
        else:
            total = df.iloc[i, 2]
            vacant = df.iloc[i, 8]
        if total in ("-", "nan") or pd.isna(total):
            continue
        total = int(float(total))
        vacant = 0 if vacant in ("-", "nan") or pd.isna(vacant) else int(float(vacant))
        rows.append(
            {
                "code": code,
                "name": name,
                "total": total,
                "vacant": vacant,
                "vac_rate": vacant / total if total else 0.0,
            }
        )
    return rows


def aggregate(muni: list[dict], zone_map: dict[str, str]) -> tuple[dict, list[dict]]:
    mapped: list[dict] = []
    missing: list[str] = []
    for r in muni:
        z = zone_map.get(r["name"])
        if not z:
            missing.append(r["name"])
            continue
        rr = dict(r)
        rr["zone"] = z
        mapped.append(rr)
    if missing:
        print(f"  WARN unmapped: {missing}")
    acc: dict[str, dict] = {z: {"total": 0, "vacant": 0, "n": 0} for z in ZONE_ORDER}
    for r in mapped:
        a = acc[r["zone"]]
        a["total"] += r["total"]
        a["vacant"] += r["vacant"]
        a["n"] += 1
    zones = {}
    for z in ZONE_ORDER:
        a = acc[z]
        rate = a["vacant"] / a["total"] if a["total"] else None
        zones[z] = {
            "vac_rate": rate,
            "total_dwellings": a["total"],
            "vacant_dwellings": a["vacant"],
            "municipality_count": a["n"],
        }
    return zones, mapped


def main() -> None:
    zone_map = load_zone_map()
    waves_out: dict[str, dict] = {}
    csv_rows: list[list] = []

    for year in sorted(WAVES):
        meta = WAVES[year]
        ensure_file(meta)
        parser = meta["parser"]
        if parser == "tokyo_pref_xls":
            muni = parse_tokyo_pref_xls(meta["file"])
        else:
            muni = parse_national_1_2(meta["file"])
        zones, mapped = aggregate(muni, zone_map)
        rates = [zones[z]["vac_rate"] for z in ZONE_ORDER]
        overall_t = sum(zones[z]["total_dwellings"] for z in ZONE_ORDER)
        overall_v = sum(zones[z]["vacant_dwellings"] for z in ZONE_ORDER)
        overall = overall_v / overall_t if overall_t else None
        print(
            f"{year}: muni={len(mapped)} overall={overall:.4f} "
            + " ".join(f"{z[:2]}={zones[z]['vac_rate']:.3f}" for z in ZONE_ORDER if zones[z]["vac_rate"] is not None)
        )
        waves_out[str(year)] = {
            "year": year,
            "survey": meta["label"],
            "table": meta["table"],
            "statInfId": meta["statInfId"],
            "source": f"https://www.e-stat.go.jp/stat-search/files?stat_infid={meta['statInfId']}",
            "overall": overall,
            "rates": rates,
            "names": ZONE_ORDER,
            "zones": zones,
            "municipality_count": len(mapped),
        }
        for z in ZONE_ORDER:
            csv_rows.append(
                [
                    year,
                    z,
                    f"{zones[z]['vac_rate']:.6f}" if zones[z]["vac_rate"] is not None else "",
                    zones[z]["total_dwellings"],
                    zones[z]["vacant_dwellings"],
                    zones[z]["municipality_count"],
                    meta["statInfId"],
                ]
            )

    payload = {
        "method": "walkforward",
        "nickname": "大学受験過去問理論",
        "description": "Wave t で初期化→5年シミュ→wave t+5 の地域別空き家率と比較。パラメータ更新は未知の次波を見せない。",
        "zone_order": ZONE_ORDER,
        "acquired": date.today().isoformat(),
        "hops": [
            {"from": 2008, "to": 2013, "years": 5},
            {"from": 2013, "to": 2018, "years": 5},
            {"from": 2018, "to": 2023, "years": 5},
        ],
        "waves": waves_out,
    }

    # Composition shares: reuse 2023 type mix as approx for older waves (documented)
    text = (ROOT / "data" / "zones_vac.gen.js").read_text(encoding="utf-8")

    def grab(key: str) -> list[float]:
        m = re.search(rf"{key}:\s*\[([^\]]+)\]", text)
        return [float(x) for x in m.group(1).split(",")] if m else [0.45] * 6

    payload["compositionFrom"] = "2023_vac_types"
    payload["negFrac"] = grab("negFrac")
    payload["saleFrac"] = grab("saleFrac")
    payload["listFrac"] = grab("listFrac")

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with OUT_CSV.open("w", encoding="utf-8") as f:
        f.write("year,zone,vac_rate,total_dwellings,vacant_dwellings,municipality_count,statInfId\n")
        for r in csv_rows:
            f.write(",".join(map(str, r)) + "\n")

    js = (
        "/* AUTO-GENERATED by scripts/build_zones_vac_walkforward.py */\n"
        '"use strict";\n'
        "(function (root) {\n"
        f"  root.ZONES_VAC_WAVES = {json.dumps(payload, ensure_ascii=False)};\n"
        "})(typeof globalThis !== \"undefined\" ? globalThis : typeof self !== \"undefined\" ? self : this);\n"
    )
    OUT_JS.write_text(js, encoding="utf-8")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_CSV}")
    print(f"Wrote {OUT_JS}")


if __name__ == "__main__":
    main()
