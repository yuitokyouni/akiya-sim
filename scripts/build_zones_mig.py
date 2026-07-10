#!/usr/bin/env python3
"""Aggregate 住基人口移動報告 (table 1) into 6-zone mig coefficients."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "ju24qv0100.csv"
OUT = ROOT / "data" / "zones_mig.csv"
MAP_DOC = ROOT / "docs" / "zone_municipality_map.md"
MAP_JSON = ROOT / "data" / "zone_municipality_map.json"

SOURCE_URL = "https://www.toukei.metro.tokyo.lg.jp/jugoki/2024/ju24q10000.htm"
SOURCE_CSV = "https://www.toukei.metro.tokyo.lg.jp/jugoki/2024/ju24qv0100.csv"
ACQUIRED = date.today().isoformat()
FISCAL_YEAR = "令和6年"

# 6 zones in model order (west → east). Islands excluded.
ZONE_MAP: dict[str, str] = {
    # 西多摩 — 西多摩エリア (都振興プラン区分)
    "青梅市": "西多摩",
    "福生市": "西多摩",
    "羽村市": "西多摩",
    "あきる野市": "西多摩",
    "瑞穂町": "西多摩",
    "日の出町": "西多摩",
    "檜原村": "西多摩",
    "奥多摩町": "西多摩",
    # 多摩中部 — 北多摩西部・北部 + 南多摩
    "八王子市": "多摩中部",
    "立川市": "多摩中部",
    "昭島市": "多摩中部",
    "国分寺市": "多摩中部",
    "国立市": "多摩中部",
    "東大和市": "多摩中部",
    "武蔵村山市": "多摩中部",
    "小平市": "多摩中部",
    "東村山市": "多摩中部",
    "清瀬市": "多摩中部",
    "東久留米市": "多摩中部",
    "西東京市": "多摩中部",
    "町田市": "多摩中部",
    "日野市": "多摩中部",
    "多摩市": "多摩中部",
    "稲城市": "多摩中部",
    # 多摩東部 — 北多摩南部 (23区に最も近い)
    "武蔵野市": "多摩東部",
    "三鷹市": "多摩東部",
    "府中市": "多摩東部",
    "調布市": "多摩東部",
    "小金井市": "多摩東部",
    "狛江市": "多摩東部",
    # 区部西
    "渋谷区": "区部西",
    "目黒区": "区部西",
    "世田谷区": "区部西",
    "中野区": "区部西",
    "杉並区": "区部西",
    "豊島区": "区部西",
    "練馬区": "区部西",
    "板橋区": "区部西",
    "北区": "区部西",
    "品川区": "区部西",
    # 都心
    "千代田区": "都心",
    "中央区": "都心",
    "港区": "都心",
    "新宿区": "都心",
    "文京区": "都心",
    # 城東
    "台東区": "城東",
    "墨田区": "城東",
    "江東区": "城東",
    "大田区": "城東",
    "荒川区": "城東",
    "足立区": "城東",
    "葛飾区": "城東",
    "江戸川区": "城東",
}

ZONE_ORDER = ["西多摩", "多摩中部", "多摩東部", "区部西", "都心", "城東"]

# モデル域外（島嶼部）— 集計から除外
EXCLUDED = {
    "大島町", "利島村", "新島村", "神津島村", "三宅村", "御蔵島村",
    "八丈町", "青ヶ島村", "小笠原村",
}


def load_municipal_rows(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    rows = list(csv.reader(text.splitlines()))
    header = rows[0]
    out: list[dict] = []
    for row in rows[1:]:
        if len(row) < 19 or not row[1].isdigit():
            continue
        if row[0] != "4":
            continue
        out.append(
            {
                "code": row[1],
                "name": row[2],
                "pop_end": int(row[3]),
                "net_ext": int(row[5]),
                "net_int": int(row[8]),
                "pop_start": int(row[18].strip()),
            }
        )
    return out


def aggregate(rows: list[dict]) -> dict[str, dict]:
    acc: dict[str, dict] = {
        z: {"pop_start": 0, "pop_end": 0, "net_mig": 0, "municipalities": []}
        for z in ZONE_ORDER
    }
    unmapped: list[str] = []
    for r in rows:
        if r["name"] in EXCLUDED:
            continue
        zone = ZONE_MAP.get(r["name"])
        if zone is None:
            unmapped.append(r["name"])
            continue
        a = acc[zone]
        a["pop_start"] += r["pop_start"]
        a["pop_end"] += r["pop_end"]
        a["net_mig"] += r["net_ext"] + r["net_int"]
        a["municipalities"].append(r["name"])

    if unmapped:
        raise SystemExit(f"Unmapped municipalities: {unmapped}")

    for z in ZONE_ORDER:
        a = acc[z]
        denom = (a["pop_start"] + a["pop_end"]) / 2
        a["mig"] = a["net_mig"] / denom if denom else 0.0
    return acc


def write_csv(agg: dict[str, dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "zone",
                "mig",
                "net_migration",
                "pop_start",
                "pop_end",
                "municipality_count",
                "source_url",
                "source_csv",
                "fiscal_year",
                "acquired_date",
            ]
        )
        for z in ZONE_ORDER:
            a = agg[z]
            w.writerow(
                [
                    z,
                    f"{a['mig']:.6f}",
                    a["net_mig"],
                    a["pop_start"],
                    a["pop_end"],
                    len(a["municipalities"]),
                    SOURCE_URL,
                    SOURCE_CSV,
                    FISCAL_YEAR,
                    ACQUIRED,
                ]
            )


def write_map_docs() -> None:
    MAP_JSON.parent.mkdir(parents=True, exist_ok=True)
    by_zone = {z: [] for z in ZONE_ORDER}
    for m, z in sorted(ZONE_MAP.items()):
        by_zone[z].append(m)
    MAP_JSON.write_text(
        json.dumps(
            {
                "description": "東京都区市町村 → ABM 6地域区分",
                "source_note": "多摩は都『新しい多摩の振興プラン』5エリアを3+3に再編。23区は都心5区+区部西10区+城東8区。島嶼部はモデル域外のため除外。",
                "zones": by_zone,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    lines = [
        "# 区市町村 → 6地域 対応表",
        "",
        "ABM `ZONES` 定数（西多摩 / 多摩中部 / 多摩東部 / 区部西 / 都心 / 城東）への割当。",
        "島嶼部（大島・三宅・八丈・小笠原等）はモデル本土部シルエットの域外マスクのため除外。",
        "",
        "## 根拠",
        "",
        "- 多摩30市町村: 都総務局『新しい多摩の振興プラン』の5エリア区分を、モデル3区分に再編",
        "  - 西多摩 = 西多摩エリア（8市町村）",
        "  - 多摩中部 = 北多摩西部・北部 + 南多摩（16市）",
        "  - 多摩東部 = 北多摩南部（6市、23区に最も近い）",
        "- 23区: 都心5区 + 区部西10区 + 城東8区（商業・住宅の様式化勾配に合わせた便宜区分）",
        "",
        "## 対応一覧",
        "",
    ]
    for z in ZONE_ORDER:
        muns = sorted(m for m, zz in ZONE_MAP.items() if zz == z)
        lines.append(f"### {z}（{len(muns)}）")
        lines.append("")
        lines.append(", ".join(muns))
        lines.append("")
    MAP_DOC.parent.mkdir(parents=True, exist_ok=True)
    MAP_DOC.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    rows = load_municipal_rows(RAW)
    agg = aggregate(rows)
    write_csv(agg, OUT)
    write_map_docs()
    print("zone,mig")
    for z in ZONE_ORDER:
        print(f"{z},{agg[z]['mig']:.6f}")


if __name__ == "__main__":
    main()
