---
title: "Zennの記事をGitHub Pagesに自動同期するCIの構築方法"
emoji: "🔄"
type: "tech"
topics: ["github", "ci", "github-actions", "zenn", "github-pages"]
published: true
---

# Zenn の記事を GitHub Pages に自動同期する CI の構築方法

## はじめに

Zenn で記事を書いていると、同じ内容を GitHub Pages のブログでも公開したい場合があります。この記事では、GitHub Actions を使用して、Zenn の記事を自動的に GitHub Pages のブログに同期する CI の構築方法について解説します。

## 前提条件

- Zenn の記事を管理する GitHub リポジトリ
- GitHub Pages のブログ用リポジトリ
- GitHub Personal Access Token (PAT)

## CI の構築手順

### 1. GitHub Personal Access Token の作成

1. GitHub の設定画面から「Developer settings」→「Personal access tokens」→「Tokens (classic)」を選択
2. 「Generate new token」をクリック
3. 以下の設定でトークンを作成：
   - Note: `Zenn to GitHub Pages Sync`
   - Expiration: 適切な有効期限を設定
   - Scopes: `repo`にチェック

### 2. リポジトリにシークレットを追加

1. Zenn の記事を管理するリポジトリの設定画面を開く
2. 「Secrets and variables」→「Actions」を選択
3. 「New repository secret」をクリック
4. 以下の設定でシークレットを追加：
   - Name: `GH_PAT`
   - Value: 先ほど作成した PAT を入力

### 3. GitHub Actions ワークフローの作成

`.github/workflows/sync-articles.yml`ファイルを作成し、以下の内容を記述します：

```yaml
name: Sync Articles to GitHub Pages

on:
  push:
    branches:
      - main
    paths:
      - "articles/**"

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout source repository
        uses: actions/checkout@v3

      - name: Checkout target repository
        uses: actions/checkout@v3
        with:
          repository: long-910/long-910.github.io
          path: target
          token: ${{ secrets.GH_PAT }}

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: "18"

      - name: Install dependencies
        run: |
          npm install -g zenn-cli

      - name: Process and sync articles
        run: |
          # 記事ファイルを処理
          for file in articles/*.md; do
            if [ -f "$file" ]; then
              # ファイル名から日付を抽出（例：2024-03-21-article-title.md）
              filename=$(basename "$file")
              date_part=$(echo "$filename" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}')
              
              if [ -n "$date_part" ]; then
                # 新しいファイル名を生成（YYYY-MM-DD-title.md形式）
                new_filename="${date_part}-$(echo "$filename" | sed "s/$date_part-//")"
                
                # フロントマターを変換
                sed -i '1s/^---/---\nlayout: post\n/' "$file"
                
                # ファイルをコピー
                cp "$file" "target/_posts/$new_filename"
              fi
            fi
          done

      - name: Commit and push changes
        run: |
          cd target
          git config --global user.name "GitHub Actions"
          git config --global user.email "actions@github.com"
          git add _posts/
          git commit -m "Sync articles from Zenn repository" || echo "No changes to commit"
          git push
```

### 4. ワークフローの説明

このワークフローは以下のように動作します：

1. **トリガー**:

   - `main`ブランチへのプッシュ
   - `articles`ディレクトリ内のファイルが変更された場合のみ実行

2. **処理の流れ**:

   - ソースリポジトリ（Zenn 記事）をチェックアウト
   - ターゲットリポジトリ（GitHub Pages）をチェックアウト
   - Node.js 環境のセットアップ
   - zenn-cli のインストール
   - 記事ファイルの処理と同期
   - 変更のコミットとプッシュ

3. **記事の変換処理**:
   - ファイル名から日付を抽出
   - フロントマターに`layout: post`を追加
   - 変換された記事をターゲットリポジトリにコピー

## 記事の作成ルール

この CI を正しく動作させるために、以下のルールに従って記事を作成する必要があります：

1. **ファイル名の形式**:

   - `YYYY-MM-DD-title.md`の形式で作成
   - 例：`2024-03-21-zenn-github-pages-sync-ci.md`

2. **フロントマター**:
   - Zenn の形式のフロントマターを使用
   - CI が自動的に`layout: post`を追加

## 動作確認方法

1. 新しい記事を作成してプッシュ
2. GitHub Actions の実行状況を確認
3. ターゲットリポジトリに記事が同期されていることを確認

## 注意点

1. **セキュリティ**:

   - PAT は適切なスコープのみを付与
   - 定期的に PAT をローテーション

2. **ファイル名**:

   - 日付形式は必ず`YYYY-MM-DD`に従う
   - ファイル名に日本語は使用しない

3. **フロントマター**:
   - Zenn の形式を維持
   - 必要なメタデータは全て含める

## まとめ

この CI を導入することで、以下のメリットが得られます：

- 記事の一元管理が可能
- 手動での同期作業が不要
- 記事の公開プロセスが自動化
- ミスのリスクを低減

## 参考リンク

- [GitHub Actions 公式ドキュメント](https://docs.github.com/ja/actions)
- [Zenn CLI 公式ドキュメント](https://zenn.dev/zenn/articles/zenn-cli-guide)
- [GitHub Pages 公式ドキュメント](https://docs.github.com/ja/pages)
