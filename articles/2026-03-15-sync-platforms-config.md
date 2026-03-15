---
title: "ファイル1つで全プラットフォームの同期先を管理する設定ファイルを導入した"
emoji: "🎛️"
type: "tech"
topics: ["githubactions", "automation", "zenn", "qiita", "hatenablog"]
published: false
published_at: "2026-03-15 15:00"
---

:::message
この記事は **Claude Code**（claude.ai/code）を使用して作成しました。
:::

## 背景

Zenn記事の同期先として GitHub Pages・Qiita・はてなブログ・note.com への自動投稿を構築してきました。

しかし、どこに同期するかを制御するには GitHub の Variables 設定画面に入る必要があり、リポジトリを見ただけでは「今どこに投稿されているのか」がわからない問題がありました。

今回、設定を **リポジトリ内の JSON ファイル1つ** に一元化しました。

---

## 設定ファイル: `.github/sync-platforms.json`

```json
{
  "platforms": {
    "github_pages": {
      "enabled": true,
      "exclude_articles": [
        "2025-06-06-yazi.md"
      ]
    },
    "qiita": {
      "enabled": false,
      "exclude_articles": []
    },
    "hatena": {
      "enabled": false,
      "exclude_articles": []
    },
    "note": {
      "enabled": false,
      "exclude_articles": []
    }
  }
}
```

### フィールドの説明

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `platforms.{name}.enabled` | boolean | そのプラットフォームへの自動投稿を有効にするか |
| `platforms.{name}.exclude_articles` | string[] | このプラットフォームへの投稿から除外するファイル名のリスト |

---

## 使い方

### プラットフォームを有効化する

Qiita への自動投稿を始めたい場合、`enabled` を `true` に変えて commit するだけです：

```json
"qiita": {
  "enabled": true,
  "exclude_articles": []
}
```

### 特定記事を除外する

個人的な記録記事など、Qiita には投稿したくない記事があれば `exclude_articles` に追加します：

```json
"qiita": {
  "enabled": true,
  "exclude_articles": [
    "2025-06-06-yazi.md",
    "2026-01-01-diary.md"
  ]
}
```

### 全プラットフォームを一時停止する

メンテナンス時など、すべてを止めたい場合は全部 `false` にします：

```json
{
  "platforms": {
    "github_pages": { "enabled": false, "exclude_articles": [] },
    "qiita":        { "enabled": false, "exclude_articles": [] },
    "hatena":       { "enabled": false, "exclude_articles": [] },
    "note":         { "enabled": false, "exclude_articles": [] }
  }
}
```

---

## 仕組み

### GitHub Actions での読み取り

各ワークフローは checkout 直後に `jq` でこのファイルを読み、`enabled` が `false` なら後続ステップをすべてスキップします：

```yaml
- name: Check if Qiita posting is enabled
  id: config
  run: |
    ENABLED=$(jq -r '.platforms.qiita.enabled' .github/sync-platforms.json)
    echo "enabled=$ENABLED" >> "$GITHUB_OUTPUT"

- name: Set up Python
  if: steps.config.outputs.enabled == 'true'
  uses: actions/setup-python@v5
  ...
```

`enabled: false` のときは Python のセットアップすら行わないため、ジョブの実行時間を無駄にしません。

### Python スクリプトでの読み取り

手動投稿スクリプトも `exclude_articles` を参照し、除外リストに含まれる記事はスキップします：

```python
SYNC_PLATFORMS_FILE = REPO_ROOT / ".github" / "sync-platforms.json"

def is_excluded(filename: str) -> bool:
    if not SYNC_PLATFORMS_FILE.exists():
        return False
    with open(SYNC_PLATFORMS_FILE) as f:
        config = json.load(f)
    exclude_list = (
        config.get("platforms", {})
        .get(PLATFORM_NAME, {})
        .get("exclude_articles", [])
    )
    return filename in exclude_list
```

`--all` で全記事を一括投稿するときに、除外リストの記事が混入するのを防ぎます。

### 設定ファイルの変更もトリガーになる

各ワークフローのトリガーには `sync-platforms.json` の変更も含まれています：

```yaml
on:
  push:
    paths:
      - "articles/*.md"
      - ".github/sync-platforms.json"  # ← これ
```

`enabled` を `false → true` に変更して push するだけで、最後のコミット差分にある記事が自動で投稿されます。

---

## 以前の構成との違い

| 項目 | 以前 | 現在 |
|------|------|------|
| 有効/無効の設定場所 | GitHub Variables（Settings画面） | `.github/sync-platforms.json` |
| 設定の可視性 | リポジトリから見えない | リポジトリに記録される ✅ |
| バージョン管理 | されない | git で履歴管理される ✅ |
| 変更の反映 | Settings画面を操作 | ファイルを編集して push ✅ |
| 除外記事の管理 | `sync-config.json`（GitHub Pages のみ） | `sync-platforms.json` でプラットフォームごとに管理 ✅ |

---

## 全体構成まとめ

```
.github/sync-platforms.json   ← ここを編集するだけで同期先を制御
    │
    ├── github_pages.enabled  → sync-articles.yml
    ├── qiita.enabled         → auto-post-qiita.yml
    ├── hatena.enabled        → auto-post-hatena.yml
    └── note.enabled          → auto-post-note.yml
```

設定ファイルを1つ編集して push するだけで、どのプラットフォームに記事を配信するかをコードとして管理できるようになりました。

---

## シリーズ記事

1. [マルチプラットフォーム配信の全体概要](https://zenn.dev/long910/articles/2026-03-15-multi-platform-blog-strategy)
2. [ZennからQiita自動同期投稿](https://zenn.dev/long910/articles/2026-03-15-qiita-auto-posting)
3. [ZennからはてなブログAtomPub自動投稿](https://zenn.dev/long910/articles/2026-03-15-hatena-auto-posting)
4. **この記事: 設定ファイルで同期先を一元管理**
