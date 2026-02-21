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
