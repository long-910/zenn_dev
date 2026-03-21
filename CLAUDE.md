# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Zenn articles repository for user `long910`. Articles written here are published to [Zenn](https://zenn.dev/long910) via GitHub integration, and also synced to a separate GitHub Pages repository (`long-910/long-910.github.io`) via a CI workflow.

## Common Commands

```bash
# Install dependencies
npm install

# Create a new article
npx zenn new:article

# Preview articles locally (opens browser at localhost)
npx zenn preview
```

## Article Format

All articles live in `articles/` as Markdown files. The filename convention is `YYYY-MM-DD-slug.md`.

Required frontmatter for every article:

```yaml
---
title: "記事タイトル"
emoji: "🔖"
type: "tech"       # tech: 技術記事 / idea: アイデア
topics: ["tag1", "tag2"]
published: true
published_at: "2025-05-25 01:10"
---
```

- `type` must be `"tech"` or `"idea"`
- `topics` are Zenn tags (array of strings)
- `published: false` keeps the article as a draft on Zenn
- `published_at` controls the display date/time

## Article Writing Rules

**DO NOT** include the following message block in any article:

```markdown
:::message
この記事は **Claude Code**（claude.ai/code）を使用して作成しました。
:::
```

This block must **not** be added to any article.

## Platform Sync (Qiita / Hatena / note / WeChat / Zhihu / CSDN)

記事を `main` にプッシュすると各プラットフォームへの自動投稿ワークフローが起動する。

### 追跡ファイルの管理

各プラットフォームの投稿済み記事を管理する `scripts/*-posted.json` は、**`tracking-data` ブランチ**に保存される（`main` には含まれない）。これにより、追跡ファイルの更新が Zenn の GitHub 連携 webhook を無駄に発火させるのを防いでいる。

### ローカルでスクリプトを実行する場合

```bash
# 1. 実行前: tracking-data ブランチから最新の追跡JSONを取得
./scripts/fetch-tracking.sh

# 2. スクリプト実行
python scripts/post-to-qiita.py articles/2026-01-01-example.md

# 3. 実行後: 更新した追跡JSONを tracking-data ブランチに保存
./scripts/push-tracking.sh
```

fetch/push スクリプトは全プラットフォーム分をまとめて処理する。複数スクリプトを連続実行した場合も、最後に `push-tracking.sh` を一度呼べばよい。

### 手動同期 (manual-sync.yml)

GitHub Actions の `workflow_dispatch` から実行する。`main` へのプッシュは発生しないため、Zenn には影響しない。

## GitHub Pages Sync

On push to `main`, the workflow `.github/workflows/sync-articles.yml` automatically:
1. Reads exclude list from `.github/sync-config.json`
2. Transforms Zenn frontmatter → Jekyll frontmatter (layout, category, tags, date, image fields)
3. Prepends a cross-link back to the Zenn article
4. Copies transformed files to `_posts/` in the `long-910/long-910.github.io` repo

The workflow requires a `GH_PAT` secret (classic PAT with `repo` scope) configured in this repository's Actions secrets.

### Excluding articles from sync

To prevent an article from being synced to GitHub Pages, add its filename to `.github/sync-config.json`:

```json
{
  "exclude_articles": [
    "2025-06-06-yazi.md"
  ]
}
```
