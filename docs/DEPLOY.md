# 公開デプロイ（localhost 脱却）

静的 HTML のみ。**GitHub Pages** で公開します。

## 公開 URL

**https://yuitokyouni.github.io/akiya-sim/**

（`main` への push で `gh-pages` ブランチに自動デプロイ）

## 初回のみ（リポジトリ管理者）

1. GitHub → **Settings → Pages**
2. **Build and deployment → Source**: `Deploy from a branch`
3. **Branch**: `gh-pages` / `/ (root)` → **Save**

※ 初回 push 後に `gh-pages` ブランチが作成されます。ブランチが無いうちは設定できません。

## ローカル確認

```bash
python3 -m http.server 8765
# http://localhost:8765/
```

## ワークフロー

`.github/workflows/pages.yml` — `main` push 時に `peaceiris/actions-gh-pages` で静的ファイルを `gh-pages` へ。

## 注意

- 地理院タイルはブラウザから直接取得。オフライン時は背景なしでカラム表示は継続。
- `data/raw/` はデプロイ対象外（サイズ削減）。生成済み `*.gen.js` は含まれる。
