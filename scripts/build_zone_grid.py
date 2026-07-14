#!/usr/bin/env python3
"""Rasterize N03 Tokyo administrative boundaries onto the 84×26 ABM grid.

Outputs:
  data/zone_grid.json       — zone index per cell (-1 = mask)
  data/cells_muni.csv       — cell ↔ municipality ↔ zone mapping
  data/zone_grid.gen.js     — Int8Array for browser/node (included before engine.js)

Engine simulation logic is unchanged; only zone[] initialization is replaced.
"""

from __future__ import annotations

import csv
import json
import zipfile
from datetime import date
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
RAW_ZIP = ROOT / "data" / "raw" / "N03-20240101_13_GML.zip"
RAW_DIR = ROOT / "data" / "raw" / "n03_13"
GEOJSON = RAW_DIR / "N03-20240101_13.geojson"
MAP_JSON = ROOT / "data" / "zone_municipality_map.json"
OUT_JSON = ROOT / "data" / "zone_grid.json"
OUT_CSV = ROOT / "data" / "cells_muni.csv"
OUT_JS = ROOT / "data" / "zone_grid.gen.js"
ENGINE = ROOT / "engine.js"

W, H = 84, 26
N = W * H

# Same affine as map.html — display bbox; N03 本土部はこの範囲内に収まる
AFFINE = {"lon0": 138.95, "lon1": 139.93, "latN": 35.82, "latS": 35.53}

SOURCE_URL = "https://nlftp.mlit.go.jp/ksj/gml/data/N03/N03-2024/N03-20240101_13_GML.zip"
SOURCE_YEAR = "2024（令和6年）"
ACQUIRED = date.today().isoformat()

ZONE_ORDER = ["西多摩", "多摩中部", "多摩東部", "区部西", "都心", "城東"]

# Islands — model mask (same as build_zones_mig.py)
EXCLUDED = {
    "大島町", "利島村", "新島村", "神津島村", "三宅村", "御蔵島村",
    "八丈町", "青ヶ島村", "小笠原村",
}

# Municipality name → 6-zone (aligned with data/zone_municipality_map.json)
ZONE_BY_NAME: dict[str, str] = {}
for zone_name, muns in json.loads(MAP_JSON.read_text(encoding="utf-8"))["zones"].items():
    for m in muns:
        ZONE_BY_NAME[m] = zone_name


def grid_to_lnglat(x: int, y: int) -> tuple[float, float]:
    lon = AFFINE["lon0"] + (x / (W - 1)) * (AFFINE["lon1"] - AFFINE["lon0"])
    lat = AFFINE["latN"] - (y / (H - 1)) * (AFFINE["latN"] - AFFINE["latS"])
    return lon, lat


def ensure_geojson() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if GEOJSON.exists():
        return
    if not RAW_ZIP.exists():
        import urllib.request
        print(f"Downloading {SOURCE_URL} ...")
        urllib.request.urlretrieve(SOURCE_URL, RAW_ZIP)
    with zipfile.ZipFile(RAW_ZIP) as zf:
        zf.extractall(RAW_DIR)


def load_municipality_polygons() -> gpd.GeoDataFrame:
    ensure_geojson()
    gdf = gpd.read_file(GEOJSON)
    gdf = gdf[gdf["N03_004"].notna() & (gdf["N03_004"] != "所属未定地")].copy()
    gdf["name"] = gdf["N03_004"]
    gdf["code"] = gdf["N03_007"].astype(str)
    dissolved = (
        gdf.dissolve(by=["code", "name"], as_index=False)[["code", "name", "geometry"]]
    )
    dissolved = dissolved[~dissolved["name"].isin(EXCLUDED)].copy()
    dissolved["zone_name"] = dissolved["name"].map(ZONE_BY_NAME)
    unmapped = dissolved[dissolved["zone_name"].isna()]["name"].unique().tolist()
    if unmapped:
        raise SystemExit(f"Unmapped municipalities in N03: {unmapped}")
    dissolved["zone_id"] = dissolved["zone_name"].map({z: i for i, z in enumerate(ZONE_ORDER)})
    return dissolved


def rasterize(muni: gpd.GeoDataFrame) -> tuple[list[int], list[dict]]:
    zone = [-1] * N
    cells: list[dict] = []

    # Build spatial index via unary union per zone not needed; query each muni
    geoms = list(muni.geometry)
    codes = list(muni["code"])
    names = list(muni["name"])
    zone_ids = list(muni["zone_id"])
    zone_names = list(muni["zone_name"])

    for y in range(H):
        for x in range(W):
            i = y * W + x
            lon, lat = grid_to_lnglat(x, y)
            pt = Point(lon, lat)
            hit = None
            for gi, geom in enumerate(geoms):
                if geom.contains(pt) or geom.touches(pt):
                    hit = gi
                    break
            if hit is None:
                zone[i] = -1
                cells.append({
                    "i": i, "x": x, "y": y, "lon": round(lon, 6), "lat": round(lat, 6),
                    "muni_code": "", "muni_name": "", "zone_id": -1, "zone_name": "",
                })
            else:
                zid = int(zone_ids[hit])
                zone[i] = zid
                cells.append({
                    "i": i, "x": x, "y": y, "lon": round(lon, 6), "lat": round(lat, 6),
                    "muni_code": codes[hit], "muni_name": names[hit],
                    "zone_id": zid, "zone_name": zone_names[hit],
                })
    return zone, cells


def zone_stats(zone: list[int]) -> dict:
    counts = {z: 0 for z in ZONE_ORDER}
    mask = 0
    for v in zone:
        if v < 0:
            mask += 1
        else:
            counts[ZONE_ORDER[v]] += 1
    active = N - mask
    return {"active_cells": active, "mask_cells": mask, "by_zone": counts}


def write_zone_grid_json(zone: list[int], stats: dict) -> None:
    OUT_JSON.write_text(
        json.dumps(
            {
                "W": W,
                "H": H,
                "N": N,
                "affine": AFFINE,
                "source": {
                    "dataset": "国土数値情報 N03 行政区域",
                    "url": SOURCE_URL,
                    "year": SOURCE_YEAR,
                    "acquired_date": ACQUIRED,
                    "note": "島嶼部除外。格子は map.html と同一アフィン射影。",
                },
                "stats": stats,
                "zone": zone,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def write_cells_csv(cells: list[dict]) -> None:
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["i", "x", "y", "lon", "lat", "muni_code", "muni_name", "zone_id", "zone_name"],
        )
        w.writeheader()
        w.writerows(cells)


def write_zone_grid_js(zone: list[int]) -> None:
    body = ", ".join(str(v) for v in zone)
    aff = json.dumps(AFFINE, ensure_ascii=False)
    OUT_JS.write_text(
        f"""/* AUTO-GENERATED by scripts/build_zone_grid.py — do not edit */
"use strict";
(function (root) {{
  root.ZONE_GRID = new Int8Array([{body}]);
  root.ZONE_GRID_META = {{ W: {W}, H: {H}, N: {N}, affine: {aff}, source: "{SOURCE_URL}" }};
}})(typeof globalThis !== "undefined" ? globalThis : typeof self !== "undefined" ? self : this);
""",
        encoding="utf-8",
    )


def patch_engine_js() -> None:
    text = ENGINE.read_text(encoding="utf-8")
    begin = "/* ZONE_GRID_BEGIN"
    end = "/* ZONE_GRID_END"
    if begin not in text:
        raise SystemExit("engine.js missing ZONE_GRID markers — add them first")
    replacement = """/* ZONE_GRID_BEGIN — generated by scripts/build_zone_grid.py; do not edit */
const zone=(typeof ZONE_GRID!=="undefined"?ZONE_GRID:(()=>{throw new Error("Load data/zone_grid.gen.js before engine.js")})());
const AFFINE=(typeof ZONE_GRID_META!=="undefined"&&ZONE_GRID_META.affine)?ZONE_GRID_META.affine:{lon0:138.95,lon1:139.93,latN:35.82,latS:35.53};
/* ZONE_GRID_END */"""
    start = text.index(begin)
    end_marker = "/* ZONE_GRID_END */"
    stop = text.index(end_marker) + len(end_marker)
    new_text = text[:start] + replacement + text[stop:]
    ENGINE.write_text(new_text, encoding="utf-8")


def main() -> None:
    muni = load_municipality_polygons()
    zone, cells = rasterize(muni)
    stats = zone_stats(zone)
    active = stats["active_cells"]
    if active < 500:
        raise SystemExit(f"Too few active cells: {active}")

    write_zone_grid_json(zone, stats)
    write_cells_csv(cells)
    write_zone_grid_js(zone)
    patch_engine_js()

    print("zone stats:", json.dumps(stats, ensure_ascii=False))
    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUT_CSV.relative_to(ROOT)}")
    print(f"Wrote {OUT_JS.relative_to(ROOT)}")
    print(f"Patched {ENGINE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
