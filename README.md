# 空き家政策シミュレータ（akiya-sim）

都知事杯オープンデータ・ハッカソン2026 向け。東京都域の様式化 ABM で空き家課税・解体補助の効果を同一シードで比較します。

## デモ URL

**https://yuitokyouni.github.io/akiya-sim/**

| ページ | 説明 |
|--------|------|
| [うちの街は10年後…](index.html) | 市民向け検索＋4枚（いま＝観測値） |
| [地図ビュー](map.html) | MapLibre + deck.gl、ベース/介入並列 |
| [マクロ動態](dynamics.html) | 時系列・所有者属性・格子ホバー |
| [メカニズム](mechanism.html) | 政策の因果経路 |
| [格子シミュレータ](akiya_abm_tokyo.html) | 軽量版 |

## 初回公開設定（管理者・1回だけ）

`gh-pages` ブランチへのデプロイは CI 済み。サイトを有効化するには:

1. GitHub → **Settings → Pages**
2. Source: **Deploy from a branch** → Branch: **`gh-pages`** / **`/ (root)`** → Save

## 開発

```bash
python3 -m http.server 8765   # http://localhost:8765/
npm test                      # 住調2023 + 政策監査 + 60年 + walkforward + いま観測
npm run build:ima             # 市区町村「いま」観測パック再生成
```

詳細: [docs/DEPLOY.md](docs/DEPLOY.md) · [Handoff_akiya.md](Handoff_akiya.md) · [docs/product_citizen_framing.md](docs/product_citizen_framing.md)
