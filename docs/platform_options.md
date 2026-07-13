# プラットフォーム移行案（単一 HTML の限界と次の選択肢）

現状の `map.html` / `akiya_abm_tokyo.html` は **単一 HTML + 生成 JS** で動く。
ハッカソン・デモには最適だが、住調2023 キャリブレーション以降の要求（出典の明示、CI 検証、
複数ビュー、セルインスペクタ等）では次の限界が見えてきた。

## 単一 HTML の限界

| 限界 | 具体例 |
|------|--------|
| **データと UI の結合** | `zone_grid.gen.js` / `zones_vac.gen.js` を手で `<script>` 順序管理。更新漏れで即クラッシュ |
| **検証の二重化** | ブラウザ用 IIFE と Node 用 `module.exports` を同一 `engine.js` で維持。ハーネスは vm サンドボックス |
| **出典・説得性の UI 化** | 統計表リンク・定義・取得日を HTML 内に埋め込むと陳腐化。サイドパネル化したい |
| **地図スタック** | deck.gl + MapLibre を CDN 直読み。バージョン固定・オフライン・テストが弱い |
| **拡張コスト** | セルクリック→属性パネル、政策スライダー、複数シナリオ比較は DOM/状態管理が膨らむ |
| **再現性の可視化** | seed・版数・ハーネス結果を UI に常時表示する仕組みが後付け |

## 推奨: 段階的移行（3 レイヤー分離）

```
data/ (CSV, JSON, 生成物)  ← Python ビルドスクリプト
engine/ (純 JS, テスト可能) ← npm パッケージ or サブモジュール
app/   (Vite + React 等)    ← 地図・チャート・出典パネル
```

### Phase A — リポジトリ内モノレポ（コスト低・効果大）

**Vite + TypeScript + React**（または Svelte）で `app/` を新設。

- `engine.js` → `packages/engine/index.js`（既存 API 維持、Jest/vitest で `harness_10y` 相当をユニット化）
- 生成データは `import zonesVac from '../data/zones_vac.json'`（`.gen.js` を JSON に統一可能）
- `map.html` はレガシーとして残し、`npm run dev` で新 UI を主戦場に
- **CI**: `harness:10y`（主）→ `harness:60y`（副）→ `smoke:map`（UI）

メリット: ホットリロード、型、コンポーネント分割、出典パネルを `ProvenancePanel.tsx` として固定。

### Phase B — 分析・説得性向け Observable / Quarto

**Observable Notebook** または **Quarto + Observable JS** で「論文・プレゼン用」ビューを分離。

- 住調2023 集計表・6 地域マップ・ハーネス出力 JSON をその場で可視化
- 「データ→モデル→検証」の narrative を 1 URL で共有（審査員・政策担当向け）
- シミュレーション本体は Phase A の engine を import

メリット: 出典・脚注・再実行ボタンが notebook 文化と相性良い。HTML 1 枚より説得性が高い。

### Phase C — 本格 GIS（余力）

- **MapLibre + deck.gl** を npm 管理（既存 `map.html` の CDN 脱却）
- **PLATEAU 3D Tiles** を本番タイルサーバ or 都 API 経由で読込
- 格子 ABM は統計レイヤーとしてオーバーレイ（「地物予測」ではない旨を UI 固定表示）

## 各選択肢の比較

| 方式 | 開発コスト | 説得性 | CI/テスト | デモ速度 |
|------|------------|--------|-----------|----------|
| 現状（単一 HTML） | 最低 | 中（doc 依存） | 中（vm ハーネス） | 最高 |
| Vite + React モノレポ | 中 | 高（UI に出典） | 高 | 高 |
| Observable / Quarto | 低〜中 | 最高（ narrative ） | 中 | 中 |
| Jupyter + PyABM 移行 | 高 | 高 | 高 | 低 |

## 当面の現実解（本リポジトリ）

1. **エンジンとデータ生成は現行維持**（Python ビルド + `engine.js`）
2. **`harness_10y.js` を CI の主ゲート**に（住調2023 t=0 + t=10 レンジ）
3. **`docs/validation_jyutaku2023.md` を UI からリンク**（map.html の notice に URL）
4. タスク 4（セルインスペクタ）着手時に **Vite 化 go/no-go** — インスペクタが DOM 複雑化のトリガー

## 移行しない方がよい場合

- 提出期限が数時間で、デモ URL 1 本だけ必要
- 審査が「動くプロトタイプ」のみで、出典・再現性の UI 表示を求めない

その場合は現行 HTML + 本ドキュメント群 + ハーネス出力 JSON の添付で足りる。
