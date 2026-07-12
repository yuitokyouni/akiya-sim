# データ

| パス | 内容 |
|------|------|
| `raw/ju24qv0100.csv` | 住基人口移動報告 令和6年 第1表（原本） |
| `raw/N03-20240101_13_GML.zip` | 国土数値情報 N03 東京都（build 時自動 DL、git 除外） |
| `zones_mig.csv` | 6地域 `mig` 集計（`scripts/build_zones_mig.py` 生成） |
| `zone_municipality_map.json` | 区市町村→6地域 対応表（機械可読） |
| `zone_grid.json` | N03 ラスタライズ zone[] + 統計 |
| `zone_grid.gen.js` | ブラウザ/node 用 `ZONE_GRID` |
| `cells_muni.csv` | セル↔区市町村コード |

| `zones_vac_jyutaku2023.csv` | 6地域 住調2023 空き家率集計 |
| `zones_vac.gen.js` | ブラウザ/node 用 `ZONES_VAC`（engine 初期化） |
| `muni_vac_jyutaku2023.csv` | 区市町村別 住調2023 空き家率 |
| `raw/jyutaku_1-2_total.xlsx` | 住調2023 第1-2表 原本（e-Stat） |

再生成:

```bash
python3 scripts/build_zones_mig.py
python3 scripts/build_zone_grid.py
python3 scripts/build_zones_vac_jyutaku2023.py
```

N03 格子: `docs/n03_zone_grid.md` — 住調キャリブレーション: `docs/validation_jyutaku2023.md`
