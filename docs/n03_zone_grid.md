# N03 由来 zone[] 格子（84×26）

手描き様式化シルエットを廃止し、国土数値情報 **N03 行政区域**（東京都、令和6年版）を
`map.html` と同一アフィン射影で 84×26 格子にラスタライズしたマスク・地域割当。

## データ源

| 項目 | 値 |
|------|-----|
| データセット | 国土数値情報 N03 行政区域 |
| URL | https://nlftp.mlit.go.jp/ksj/gml/data/N03/N03-2024/N03-20240101_13_GML.zip |
| 年度 | 2024（令和6年） |
| 除外 | 島嶼9町村（`scripts/build_zones_mig.py` の EXCLUDED と同一） |

## 格子定義

`map.html` の `AFFINE` と同一:

- lon: 138.95 → 139.93（x = 0 … 83）
- lat: 35.82 → 35.53（y = 0 … 25、北→南）

各セル中心 `(x,y)` を Point-in-polygon で N03 ポリゴンに照合し、
`data/zone_municipality_map.json` 経由で 6 地域 ID（0–5）を付与。域外・海上は `-1`。

## 生成物

| ファイル | 内容 |
|----------|------|
| `data/zone_grid.json` | zone[] + メタデータ + セル数統計 |
| `data/zone_grid.gen.js` | ブラウザ/node 用 `ZONE_GRID` Int8Array |
| `data/cells_muni.csv` | セルごとの区市町村コード・名称・地域 |
| `engine.js` | `ZONE_GRID` を参照（ロジック不変） |

## 再生成

```bash
python3 scripts/build_zone_grid.py   # 初回は N03 zip を自動 DL
node scripts/harness_60y.js          # golden 更新時は --golden で明示
```

## セル数（seed=42 時点の mask 統計）

再生成後 `data/zone_grid.json` の `stats.by_zone` を参照。
多摩東部は面積比でセル数が少なく、旧手描きシルエットより区部・多摩の境界が実境界に一致する。

## 表示（UI）

格子マップ（`akiya_abm_tokyo.html` / `dynamics.html`）は `ui/grid_map.js` で
**有効セル（zone≥0）の外接矩形にパディングを付けて描画**する。84×26 全体を
キャンバス端まで伸ばさないため、北端・南端のシルエットが切れない。

地図ビュー（`map.html`）は有効セル範囲で `fitBounds` し、シアン線でモデル対象域の外枠を表示する。

対応表は [`zone_municipality_map.md`](zone_municipality_map.md) / `data/zone_municipality_map.json`。
空間割当は N03、属性（mig 等）は別 CSV から engine の `ZONES` 定数へ反映。
