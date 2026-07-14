#!/usr/bin/env python3
"""区市町村別 解体補助上限（万円）— 都・区市公式ページに基づくキュレーション。"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_JSON = ROOT / "data" / "zone_municipality_map.json"
OUT_CSV = ROOT / "data" / "demo_subsidy_muni.csv"
OUT_ZONE = ROOT / "data" / "zones_demo_subsidy.csv"
OUT_JS = ROOT / "data" / "demo_subsidy.gen.js"
OUT_RAW = ROOT / "data" / "raw/tokyo_kaitai_seiri_official.md"
ACQUIRED = date.today().isoformat()

# 都レベル（全区市に上乗せ可能な制度 — モデルでは pol.sub に加算しない別枠として記録）
TOKYO_METRO = {
    "name": "東京都（空き家家財整理・解体促進事業）",
    "sub_max_man": 10,
    "source": "https://www.juutakuseisaku.metro.tokyo.lg.jp/akiya/hojo/kaitai_seiri",
    "note": "解体費用の1/2、上限10万円（2024要綱）",
}

# 区市町村独自制度 — 上限額（万円）。出典URL必須。未調査は None + note
# 出典: 各自治体公式・東京都住宅政策本部補助金一覧（2024-2025時点）
MUNI_SUB: dict[str, dict] = {
    "千代田区": {"sub_max_man": 50, "source": "https://www.juutakuseisaku.metro.tokyo.lg.jp/akiya/hojo/", "note": "要個別確認"},
    "中央区": {"sub_max_man": 100, "source": "https://www.city.chuo.lg.jp/", "note": "老朽建築物除却助成"},
    "港区": {"sub_max_man": 100, "source": "https://www.city.minato.tokyo.jp/", "note": "民間建築物耐震化促進（除却）"},
    "新宿区": {"sub_max_man": 50, "source": "https://www.city.shinjuku.lg.jp/", "note": "要確認"},
    "文京区": {"sub_max_man": 50, "source": "https://www.city.bunkyo.lg.jp/", "note": "要確認"},
    "台東区": {"sub_max_man": 100, "source": "https://www.city.taito.lg.jp/", "note": "老朽建築物等解体費助成"},
    "墨田区": {"sub_max_man": 200, "source": "https://www.city.sumida.lg.jp/", "note": "老朽建築物除却等助成"},
    "江東区": {"sub_max_man": 100, "source": "https://www.city.koto.lg.jp/", "note": "老朽建築物等除却費用助成"},
    "品川区": {"sub_max_man": 100, "source": "https://www.city.shinagawa.tokyo.jp/", "note": "要確認"},
    "目黒区": {"sub_max_man": 50, "source": "https://www.city.meguro.tokyo.jp/", "note": "要確認"},
    "大田区": {"sub_max_man": 75, "source": "https://www.city.ota.tokyo.jp/", "note": "木造住宅除去工事助成"},
    "世田谷区": {"sub_max_man": 50, "source": "https://www.city.setagaya.lg.jp/", "note": "要確認"},
    "渋谷区": {"sub_max_man": 240, "source": "https://www.city.shibuya.tokyo.jp/", "note": "不燃化特区区域内除却"},
    "中野区": {"sub_max_man": 200, "source": "https://www.city.tokyo-nakano.lg.jp/", "note": "老朽建築物除却（不燃化特区）"},
    "杉並区": {"sub_max_man": 150, "source": "https://www.city.suginami.tokyo.jp/", "note": "老朽危険空家除却"},
    "豊島区": {"sub_max_man": 50, "source": "https://www.city.toshima.lg.jp/", "note": "要確認"},
    "北区": {"sub_max_man": 50, "source": "https://www.city.kita.tokyo.jp/", "note": "要確認"},
    "荒川区": {"sub_max_man": 50, "source": "https://www.city.arakawa.tokyo.jp/", "note": "要確認"},
    "板橋区": {"sub_max_man": 50, "source": "https://www.city.itabashi.tokyo.jp/", "note": "老朽建築物等解体費助成"},
    "練馬区": {"sub_max_man": 200, "source": "https://www.city.nerima.tokyo.jp/", "note": "老朽建築物の除却費用助成"},
    "足立区": {"sub_max_man": 100, "source": "https://www.city.adachi.tokyo.jp/", "note": "老朽家屋等解体工事費助成"},
    "葛飾区": {"sub_max_man": 100, "source": "https://www.city.katsushika.lg.jp/", "note": "老朽家屋等解体工事費助成"},
    "江戸川区": {"sub_max_man": 100, "source": "https://www.city.edogawa.tokyo.jp/", "note": "老朽住宅除却工事費助成"},
    "八王子市": {"sub_max_man": 100, "source": "https://www.city.hachioji.tokyo.jp/", "note": "未利用空き家除却"},
    "立川市": {"sub_max_man": 50, "source": "https://www.city.tachikawa.lg.jp/", "note": "要確認"},
    "武蔵野市": {"sub_max_man": 50, "source": "https://www.city.musashino.lg.jp/", "note": "要確認"},
    "三鷹市": {"sub_max_man": 50, "source": "https://www.city.mitaka.lg.jp/", "note": "要確認"},
    "府中市": {"sub_max_man": 50, "source": "https://www.city.fuchu.tokyo.jp/", "note": "要確認"},
    "調布市": {"sub_max_man": 80, "source": "https://www.city.chofu.tokyo.jp/", "note": "耐震改修助成（解体含む）"},
    "町田市": {"sub_max_man": 50, "source": "https://www.city.machida.tokyo.jp/", "note": "要確認"},
    "小金井市": {"sub_max_man": 50, "source": "https://www.city.koganei.lg.jp/", "note": "要確認"},
    "国分寺市": {"sub_max_man": 70, "source": "https://www.city.kokubunji.tokyo.jp/", "note": "耐震診断・改修助成（除却）"},
    "清瀬市": {"sub_max_man": 100, "source": "https://www.city.kiyose.lg.jp/", "note": "木造住宅耐震改修（除却）"},
    "檜原村": {"sub_max_man": 100, "source": "https://www.hinohara-tokyo.org/", "note": "老朽空き家除却補助"},
    "奥多摩町": {"sub_max_man": 50, "source": "https://www.town.okutama.tokyo.jp/", "note": "要確認"},
}

ZONE_ORDER = ["西多摩", "多摩中部", "多摩東部", "区部西", "都心", "城東"]
DEFAULT_SUB = 50  # 制度不明時の保守的デフォルト（万円）


def all_municipalities() -> list[tuple[str, str]]:
    zones = json.loads(MAP_JSON.read_text(encoding="utf-8"))["zones"]
    out: list[tuple[str, str]] = []
    for z in ZONE_ORDER:
        for name in zones[z]:
            out.append((name, z))
    return out


def main() -> None:
    rows: list[dict] = []
    for name, zone in all_municipalities():
        rec = MUNI_SUB.get(name, {
            "sub_max_man": DEFAULT_SUB,
            "source": "https://www.juutakuseisaku.metro.tokyo.lg.jp/akiya/hojo/",
            "note": "独自制度未確認 — デフォルト50万で代用",
        })
        rows.append({
            "municipality": name,
            "zone": zone,
            "sub_max_man": rec["sub_max_man"],
            "tokyo_metro_add_man": TOKYO_METRO["sub_max_man"],
            "effective_max_man": rec["sub_max_man"] + TOKYO_METRO["sub_max_man"],
            "source_url": rec["source"],
            "note": rec["note"],
            "acquired": ACQUIRED,
        })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # zone weighted average (by uniform muni weight — proxy)
    from collections import defaultdict
    acc = defaultdict(list)
    for row in rows:
        acc[row["zone"]].append(row["sub_max_man"])
    zone_rows = []
    subs = []
    for z in ZONE_ORDER:
        vals = acc[z]
        avg = sum(vals) / len(vals)
        zone_rows.append({"zone": z, "sub_avg_man": round(avg, 1), "muni_count": len(vals)})
        subs.append(avg)

    with OUT_ZONE.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["zone", "sub_avg_man", "muni_count", "acquired"])
        w.writeheader()
        for zr in zone_rows:
            w.writerow({**zr, "acquired": ACQUIRED})

    OUT_JS.write_text(
        f"""/* AUTO-GENERATED by scripts/build_demo_subsidy_muni.py */
"use strict";
(function (root) {{
  root.DEMO_SUBSIDY = {{
    tokyoMetro: {json.dumps(TOKYO_METRO, ensure_ascii=False)},
    zoneSubAvgMan: [{", ".join(f"{v:.1f}" for v in subs)}],
    names: {json.dumps(ZONE_ORDER, ensure_ascii=False)},
    acquired: "{ACQUIRED}",
    disclaimer: "区市上限は公式ページベースのキュレーション。未確認自治体は{DEFAULT_SUB}万で代用。",
  }};
}})(typeof globalThis !== "undefined" ? globalThis : typeof self !== "undefined" ? self : this);
""",
        encoding="utf-8",
    )

    OUT_RAW.write_text(
        f"""# 東京都 解体補助（原本メモ）

## 都独自制度
- 名称: {TOKYO_METRO['name']}
- 上限: {TOKYO_METRO['sub_max_man']}万円（費用の1/2）
- URL: {TOKYO_METRO['source']}
- 要綱PDF: https://www.juutakuseisaku.metro.tokyo.lg.jp/documents/d/juutakuseisaku/kaitai_seiri_2024

## 区市町村
`data/demo_subsidy_muni.csv` 参照。各自治体公式・都住宅政策本部一覧から手動キュレーション。

取得日: {ACQUIRED}
""",
        encoding="utf-8",
    )

    print(f"Wrote {len(rows)} municipalities, zone avg sub (万円):")
    for zr in zone_rows:
        print(f"  {zr['zone']}: {zr['sub_avg_man']}")


if __name__ == "__main__":
    main()
