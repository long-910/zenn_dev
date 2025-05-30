# Zenn 記事管理リポジトリz

[![Likes](https://badgen.org/img/zenn/long910/likes?style=flat-square)](https://zenn.dev/long910)
[![Followers](https://badgen.org/img/zenn/long910/followers?style=flat-square)](https://zenn.dev/long910)
[![Articles](https://badgen.org/img/zenn/long910/articles?style=flat-square)](https://zenn.dev/long910)

このリポジトリは、Zenn の記事を管理し、GitHub Pages のブログと自動同期するための設定を含んでいます。

## 機能

- Zenn CLI を使用した記事の管理
- GitHub Pages との自動同期
- フロントマターの自動変換
- 記事の相互リンク

## 前提条件

- Node.js (v18 以上)
- npm
- Git
- GitHub アカウント
- Zenn アカウント

## セットアップ

### 1. リポジトリのクローン

```bash
git clone https://github.com/your-username/zenn-articles.git
cd zenn-articles
```

### 2. Zenn CLI のインストール

```bash
npm install -g zenn-cli
```

### 3. プロジェクトの初期化

```bash
zenn init
```

これにより、以下のような構造が作成されます：

```
.
├── articles
│   └── .gitkeep
└── books
    └── .gitkeep
```

## 記事の作成と管理

### 新規記事の作成

```bash
zenn new:article
```

このコマンドを実行すると、`articles`ディレクトリに新しい Markdown ファイルが作成されます。

### 記事のプレビュー

```bash
zenn preview
```

ローカルサーバーが起動し、ブラウザで記事のプレビューを確認できます。

### 記事の構成

記事の冒頭には、以下のようなフロントマターを記述します：

```yaml
---
title: "記事のタイトル"
emoji: "🎨"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: ["タグ1", "タグ2"]
published: true
---
```

## GitHub Pages との同期

### CI の設定

1. GitHub Personal Access Token (PAT)の作成

   - GitHub の設定画面から「Developer settings」→「Personal access tokens」→「Tokens (classic)」を選択
   - 以下の設定でトークンを作成：
     - Note: `Zenn to GitHub Pages Sync`
     - Expiration: 適切な有効期限を設定
     - Scopes: `repo`にチェック

2. リポジトリにシークレットを追加
   - リポジトリの設定画面から「Secrets and variables」→「Actions」を選択
   - `GH_PAT`という名前でシークレットを追加

### フロントマターの変換

Zenn の記事は自動的に GitHub Pages の形式に変換されます：

```yaml
# Zennのフロントマター
---
title: "記事のタイトル"
emoji: "🎨"
type: "tech"
topics: ["tag1", "tag2"]
published: true
published_at: "2024-03-21 12:00"
---
# 変換後のフロントマター
---
layout: post
title: "記事のタイトル"
img_path: /assets/img/logos
image:
  path: logo-only.svg
  width: 100%
  height: 100%
  alt: Zenn
category: [Tech]
tags: [tag1, tag2]
date: 2024-03-21 12:00
---
```

### 同期の動作

1. 記事をプッシュすると自動的に同期が開始
2. フロントマターが自動変換
3. GitHub Pages のブログに記事が同期
4. 記事の最後に Zenn へのリンクが追加

## 注意点

### ファイル名

- 日本語ファイル名は使用しないことを推奨
- スペースは使用しないことを推奨
- ファイル名は任意（日付形式の制限なし）

### フロントマター

- Zenn の形式を維持
- 必要なメタデータは全て含める
- `published: true`を設定

### セキュリティ

- PAT は適切なスコープのみを付与
- 定期的に PAT をローテーション

## トラブルシューティング

### 記事が同期されない場合

1. GitHub Actions の実行状況を確認
2. PAT の権限を確認
3. リポジトリの設定を確認

### フロントマターの変換が正しく行われない場合

1. フロントマターの形式を確認
2. 必要なメタデータが含まれているか確認
3. 変換後のフロントマターを確認

## 参考リンク

- [Zenn CLI 公式ドキュメント](https://zenn.dev/zenn/articles/zenn-cli-guide)
- [GitHub Actions 公式ドキュメント](https://docs.github.com/ja/actions)
- [GitHub Pages 公式ドキュメント](https://docs.github.com/ja/pages)

## ライセンス

MIT License
