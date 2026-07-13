# 公開デプロイ（localhost 脱却）

静的 HTML のみなので **GitHub Pages** が最も手軽です。ビルド不要（`data/*.gen.js` はリポジトリにコミット済み）。

## GitHub Pages を有効化する手順

1. リポジトリ **Settings → Pages**
2. **Source**: GitHub Actions
3. `main` にマージ後、ワークフlow `.github/workflows/pages.yml` が自動実行
4. 数分後 **https://yuitokyouni.github.io/akiya-sim/** で `index.html` が開く

## ローカル確認

```bash
python3 -m http.server 8765
# http://localhost:8765/
```

## いつ公開すべきか（判断基準）

| 公開してよい | まだ待つ |
|-------------|---------|
| ハッカソン審査・デモ URL が必要 | 大規模リファクタ直前で URL が毎日変わる |
| `npm test` が通っている | 住調キャリブレーション未完了 |
| 出典リンク・用語定義が UI にある | セルインスペクタ等で UI が激変する直前 |

**現時点の推奨**: デモ URL が必要なら **今すぐ GitHub Pages でよい**。
エンジン・データ生成はそのまま、UI は Vite 化はセルインスペクタ着手時でも遅くない（`docs/platform_options.md`）。

## 注意

- 地理院タイルはブラウザから直接取得（CORS 可）。オフラインでは地図背景なしでカラムは表示される。
- Pages では `docs/` 内の Markdown はそのままでは閲覧できない。監査文書は GitHub 上で見るか、将来 UI からリンク。
