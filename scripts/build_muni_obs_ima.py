#!/usr/bin/env python3
"""Build municipality observation pack for the citizen「いま」card.

Facts only (no simulation). Sources:
  - 住調2023 vacancy (muni_vac / types)
  - 住基 人口の動き R6 (natural / social change)
  - 住基 年齢3区分 R7-01-01 (aging rate)
  - 区市町村解体補助キュレーション

Usage: python3 scripts/build_muni_obs_ima.py
"""

from __future__ import annotations

import csv
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_JSON = ROOT / "data" / "zone_municipality_map.json"
VAC = ROOT / "data" / "muni_vac_jyutaku2023.csv"
VAC_TYPES = ROOT / "data" / "muni_vac_types_jyutaku2023.csv"
SUB = ROOT / "data" / "demo_subsidy_muni.csv"
POP = ROOT / "data" / "raw" / "ju24qv0100.csv"
AGE = ROOT / "data" / "raw" / "jy25qv0301_age3.csv"

OUT_CSV = ROOT / "data" / "muni_obs_ima.csv"
OUT_JSON = ROOT / "data" / "muni_obs_ima.json"
OUT_JS = ROOT / "data" / "muni_obs_ima.gen.js"
OUT_DOC = ROOT / "docs" / "validation_muni_obs_ima.md"

ACQUIRED = date.today().isoformat()

# Station → municipality aliases for search (curated; engine STATIONS are grid proxies)
STATIONS = [
    {"name": "立川", "aliases": ["立川駅", "たちかわ"], "muni": "立川市"},
    {"name": "吉祥寺", "aliases": ["吉祥寺駅", "きちじょうじ"], "muni": "武蔵野市"},
    {"name": "新宿", "aliases": ["新宿駅", "しんじゅく"], "muni": "新宿区"},
    {"name": "東京", "aliases": ["東京駅", "とうきょう"], "muni": "千代田区"},
    {"name": "渋谷", "aliases": ["渋谷駅", "しぶや"], "muni": "渋谷区"},
    {"name": "池袋", "aliases": ["池袋駅", "いけぶくろ"], "muni": "豊島区"},
    {"name": "八王子", "aliases": ["八王子駅"], "muni": "八王子市"},
    {"name": "町田", "aliases": ["町田駅"], "muni": "町田市"},
    {"name": "府中", "aliases": ["府中駅"], "muni": "府中市"},
    {"name": "調布", "aliases": ["調布駅"], "muni": "調布市"},
    {"name": "三鷹", "aliases": ["三鷹駅"], "muni": "三鷹市"},
    {"name": "青梅", "aliases": ["青梅駅"], "muni": "青梅市"},
]


def load_zone_map() -> dict[str, str]:
    zones = json.loads(MAP_JSON.read_text(encoding="utf-8"))["zones"]
    m: dict[str, str] = {}
    for z, names in zones.items():
        for n in names:
            m[n] = z
    return m


def num(x: str | None) -> int | None:
    if x is None:
        return None
    s = str(x).strip().replace(",", "").replace(" ", "")
    if s in ("", "-", "―", "nan"):
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def read_vac() -> dict[str, dict]:
    out: dict[str, dict] = {}
    with VAC.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["name"]] = {
                "code": r["code"],
                "name": r["name"],
                "zone": r["zone"],
                "dwellings": num(r["total"]),
                "vacant": num(r["vacant"]),
                "vac_rate": float(r["vac_rate"]),
                "imputed": r.get("imputed") == "1",
            }
    if VAC_TYPES.exists():
        with VAC_TYPES.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["name"] not in out:
                    continue
                out[r["name"]].update(
                    {
                        "other_vacant": num(r.get("other_vacant")),
                        "rent_vacant": num(r.get("rent_vacant")),
                        "sale_vacant": num(r.get("sale_vacant")),
                        "neg_frac": float(r["neg_frac"]) if r.get("neg_frac") else None,
                        "list_frac": float(r["list_frac"]) if r.get("list_frac") else None,
                        "sale_frac": float(r["sale_frac"]) if r.get("sale_frac") else None,
                    }
                )
    return out


def read_pop() -> dict[str, dict]:
    out: dict[str, dict] = {}
    with POP.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            code = (r.get("地域コード") or "").strip()
            name = (r.get("地域") or "").strip()
            # municipality rows: 5-digit codes starting 131xx / 132xx / 133xx
            if not re.fullmatch(r"13\d{3}", code):
                continue
            if code in ("13000", "13100", "13200", "13300", "13350"):
                continue
            pop = num(r.get("令和7年1月1日現在人口"))
            pop0 = num(r.get("令和６年1月1日現在人口"))
            natural = num(r.get("令和６年中の動き／自然増減"))
            births = num(r.get("令和６年中の動き／自然増減／出生数"))
            deaths = num(r.get("令和６年中の動き／自然増減／死亡数"))
            social_pref = num(r.get("令和６年中の動き／社会増減（他県との移動増減）"))
            social_tokyo = num(r.get("令和６年中の動き／都内間の移動増減"))
            pop_delta = num(r.get("令和６年中の動き／人口増減"))
            mid = None
            if pop is not None and pop0 is not None:
                mid = (pop + pop0) / 2
            out[name] = {
                "code": code,
                "pop": pop,
                "pop_prev": pop0,
                "pop_delta": pop_delta,
                "natural": natural,
                "births": births,
                "deaths": deaths,
                "social_pref": social_pref,
                "social_tokyo": social_tokyo,
                "social_net": (social_pref or 0) + (social_tokyo or 0)
                if social_pref is not None or social_tokyo is not None
                else None,
                "natural_rate": (natural / mid) if (natural is not None and mid) else None,
                "social_rate": (
                    ((social_pref or 0) + (social_tokyo or 0)) / mid
                    if mid and (social_pref is not None or social_tokyo is not None)
                    else None
                ),
                "pop_delta_rate": (pop_delta / mid) if (pop_delta is not None and mid) else None,
                "density": float(str(r.get("人口密度(1km2当たり）") or "nan").replace(",", "").strip() or "nan")
                if r.get("人口密度(1km2当たり）")
                else None,
            }
            if out[name]["density"] is not None and out[name]["density"] != out[name]["density"]:
                out[name]["density"] = None
    return out


def read_age() -> dict[str, dict]:
    out: dict[str, dict] = {}
    with AGE.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            code = (r.get("地域コード") or "").strip()
            name = (r.get("地域") or "").strip()
            if not re.fullmatch(r"13\d{3}", code) or code in ("13000", "13100", "13200", "13300", "13350"):
                continue
            young = num(r.get("年少人口(0～14歳)／総数(人)"))
            work = num(r.get("生産年齢人口(15～64歳)／総数(人)"))
            old = num(r.get("老年人口(65歳以上)／総数(人)"))
            tot = (young or 0) + (work or 0) + (old or 0)
            out[name] = {
                "young": young,
                "working": work,
                "elderly": old,
                "aging_rate": (old / tot) if tot and old is not None else None,
            }
    return out


def read_sub() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not SUB.exists():
        return out
    with SUB.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["municipality"]] = {
                "sub_max_man": num(r.get("sub_max_man")),
                "tokyo_metro_add_man": num(r.get("tokyo_metro_add_man")),
                "effective_max_man": num(r.get("effective_max_man")),
                "sub_source": r.get("source_url") or "",
                "sub_note": r.get("note") or "",
            }
    return out


def copy_vac(rate: float | None) -> str:
    if rate is None:
        return "空き家率のデータがありません"
    # 「30軒に約N軒」
    n = max(1, round(rate * 30))
    pct = rate * 100
    return f"およそ30軒に{n}軒が空き家（空き家率 {pct:.1f}%）"


def copy_aging(rate: float | None) -> str:
    if rate is None:
        return "高齢化率のデータがありません"
    pct = rate * 100
    return f"住民のうちおよそ{pct:.1f}%が65歳以上"


def copy_pop(natural: int | None, social: int | None, pop_delta: int | None) -> str:
    bits = []
    if natural is not None:
        bits.append("自然増" if natural > 0 else "自然減" if natural < 0 else "自然増減ほぼゼロ")
        bits[-1] += f"（{natural:+,}人／年）"
    if social is not None:
        bits.append("転入超過" if social > 0 else "転出超過" if social < 0 else "転入出ほぼ均衡")
        bits[-1] += f"（{social:+,}人／年）"
    if pop_delta is not None and not bits:
        bits.append(f"人口増減 {pop_delta:+,}人／年")
    return "、".join(bits) if bits else "人口動態のデータがありません"


def main() -> None:
    zone_map = load_zone_map()
    vac = read_vac()
    pop = read_pop()
    age = read_age()
    sub = read_sub()

    names = sorted(set(zone_map) | set(vac) | set(pop) | set(age))
    # keep mainland zone-mapped only
    names = [n for n in names if n in zone_map]

    records = []
    for name in names:
        v = vac.get(name, {})
        p = pop.get(name, {})
        a = age.get(name, {})
        s = sub.get(name, {})
        code = v.get("code") or p.get("code") or ""
        zone = zone_map[name]
        rec = {
            "code": code,
            "name": name,
            "zone": zone,
            "vac_rate": v.get("vac_rate"),
            "dwellings": v.get("dwellings"),
            "vacant": v.get("vacant"),
            "neg_frac": v.get("neg_frac"),
            "list_frac": v.get("list_frac"),
            "sale_frac": v.get("sale_frac"),
            "vac_imputed": bool(v.get("imputed")),
            "pop": p.get("pop"),
            "pop_delta": p.get("pop_delta"),
            "natural": p.get("natural"),
            "births": p.get("births"),
            "deaths": p.get("deaths"),
            "social_net": p.get("social_net"),
            "natural_rate": p.get("natural_rate"),
            "social_rate": p.get("social_rate"),
            "aging_rate": a.get("aging_rate"),
            "elderly": a.get("elderly"),
            "effective_max_man": s.get("effective_max_man"),
            "sub_note": s.get("sub_note"),
            "sub_source": s.get("sub_source"),
            "copy_vac": copy_vac(v.get("vac_rate")),
            "copy_aging": copy_aging(a.get("aging_rate")),
            "copy_pop": copy_pop(p.get("natural"), p.get("social_net"), p.get("pop_delta")),
            "sources": {
                "vacancy": "令和5年住宅・土地統計調査 第1-2表（市区町村）",
                "population": "東京都 人口の動き（令和6年中）第1表",
                "aging": "住民基本台帳による東京都の世帯と人口 令和7年1月 第3-1表",
                "subsidy": "区市町村・都の解体関連補助（キュレーション）",
            },
        }
        records.append(rec)

    # completeness
    n = len(records)
    have_vac = sum(1 for r in records if r["vac_rate"] is not None)
    have_age = sum(1 for r in records if r["aging_rate"] is not None)
    have_pop = sum(1 for r in records if r["pop"] is not None)
    have_nat = sum(1 for r in records if r["natural"] is not None)

    payload = {
        "title": "市民向け「いま」カード用・市区町村観測パック",
        "acquired": ACQUIRED,
        "unit": "市区町村（島嶼除外・6地域マップ対象）",
        "disclaimer": "ここは予測ではなく観測値です。町丁目単位の空き家率は未収録のため、検索は市区町村／主要駅まで。",
        "coverage": {
            "municipalities": n,
            "with_vacancy": have_vac,
            "with_aging": have_age,
            "with_population": have_pop,
            "with_natural_change": have_nat,
        },
        "stations": STATIONS,
        "municipalities": records,
    }

    # CSV (flat)
    fields = [
        "code", "name", "zone", "vac_rate", "dwellings", "vacant", "neg_frac",
        "pop", "pop_delta", "natural", "social_net", "natural_rate", "social_rate",
        "aging_rate", "elderly", "effective_max_man", "vac_imputed",
        "copy_vac", "copy_aging", "copy_pop",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in records:
            row = dict(r)
            for k in ("vac_rate", "neg_frac", "natural_rate", "social_rate", "aging_rate"):
                if row.get(k) is not None:
                    row[k] = f"{row[k]:.6f}"
            w.writerow(row)

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_JS.write_text(
        "/* AUTO-GENERATED by scripts/build_muni_obs_ima.py */\n"
        '"use strict";\n'
        "(function (root) {\n"
        f"  root.MUNI_OBS_IMA = {json.dumps(payload, ensure_ascii=False)};\n"
        "})(typeof globalThis !== \"undefined\" ? globalThis : typeof self !== \"undefined\" ? self : this);\n",
        encoding="utf-8",
    )

    doc = f"""# 市区町村「いま」観測パック

市民向け4枚のうち **いま** 専用。予測値は含めない。

## カバレッジ（{ACQUIRED}）

| 項目 | 件数 |
|------|------|
| 対象市区町村 | {n} |
| 空き家率あり | {have_vac} |
| 高齢化率あり | {have_age} |
| 人口あり | {have_pop} |
| 自然増減あり | {have_nat} |

## 出典

| 指標 | 出典 |
|------|------|
| 空き家率 | 令和5年住宅・土地統計調査 第1-2表（市区町村） |
| 人口・自然増減・社会増減 | 東京都「人口の動き（令和6年中）」第1表 |
| 高齢化率（65歳以上割合） | 住基「世帯と人口」令和7年1月 第3-1表 |
| 解体補助 | `demo_subsidy_muni.csv`（キュレーション） |

## 意図的に出さないもの

- **町丁目の空き家率** — 住調市区町村表では取れない。実名町丁目に予測を載せない。
- **成約件数の時系列** — 別途不動産情報ライブラリ等が必要（未接続）。
- **シミュレーション将来値** — 「このまま10年」カードの担当。

## 再生成

```bash
python3 scripts/build_muni_obs_ima.py
node scripts/harness_muni_obs_ima.js
```
"""
    OUT_DOC.write_text(doc, encoding="utf-8")
    print(f"Wrote {OUT_CSV} ({n} munis, vac={have_vac}, age={have_age}, pop={have_pop})")
    print(f"Wrote {OUT_JSON}, {OUT_JS}, {OUT_DOC}")


if __name__ == "__main__":
    main()
