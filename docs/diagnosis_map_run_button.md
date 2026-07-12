# 診断: map.html「60年実行」ボタン不応答

## 再現手順

1. リポジトリルートで `python -m http.server 8080`
2. ブラウザで `http://localhost:8080/map.html` を開く
3. 左パネルの「▶ 60年実行」をクリック（またはページ読み込み直後の自動実行を待つ）
4. 期待: 空き家率・放置・クラスタが数値表示、年スライダーで 0–60 を再生可能

## 観測された症状

| 症状 | 意味 |
|------|------|
| 統計が `–` のまま | シミュレーション未完了、または UI 更新未実行 |
| 全ボタン無反応 | 初期化 try ブロックが途中で throw → イベント束縛（359行付近）未到達 |
| 赤枠「初期化エラー: …」 | deck.gl / maplibre / engine.js の読み込み失敗 |

## コンソールエラー（確認済み）

### A. 初期化失敗系（ボタン不応答の直接原因）

| エラー | 原因 |
|--------|------|
| `Cannot read properties of undefined (reading 'prototype')` | jsdelivr `+esm` で `@deck.gl/*` を import。hammer.js 等の依存が壊れる |
| `Cannot access 'deck' before initialization` | グローバル `deck`（ライブラリ）と `let deck`（インスタンス）の名前衝突 |

いずれも **try 全体が失敗** → `btnRun.onclick` 等が未登録 → 「60年実行」含め全 UI が死ぬ。

### B. 初期化成功後

Headless Chrome（`ca48617`）では再現せず:

- 自動実行後 vac ≈ 6.9%（year 0）
- 「60年実行」再クリック → year 60 で vac ≈ 20.2%（harness golden と一致）

## 根本原因

**単独の「60年実行ロジックバグ」ではない。**

1. **主因**: map ビュー初期化（CDN ESM → standalone 化、変数名衝突）の失敗が、イベント束縛以前に throw していた。
2. **設計上の脆さ**: `runSimulation()` を `map.on("load")` にのみ依存。地図タイル/CDN が遅い・失敗すると、統計更新も遅延し「動いていない」ように見える。
3. **engine.js**: export / 読み込み順は問題なし（harness EXACT MATCH）。容疑から除外。
4. **状態競合**: `playTimer`（アニメ）実行中に再実行すると年スライダーが競合しうるが、ボタン無反応の主因ではない。

## 対応（タスク1）

- [x] standalone `dist.min.js` + `deckInstance` リネーム（`cursor/map-html-engine-0e5f`）
- [ ] `runSimulation()` を map load から切り離し、init 完了直後に実行
- [ ] `runSimulation` に try/finally（計算中…の永久 disabled 防止）
- [ ] 再実行時に `playTimer` を停止
- [ ] `scripts/smoke_map.js`: ページ読込 → 60年実行 → year 60 到達

## スモークテスト

```bash
node scripts/smoke_map.js
```

UI は harness 守備範囲外のため、出荷前は上記を手動または CI で実行する。
