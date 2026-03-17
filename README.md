# Zenn 記事リポジトリ

[![Likes](https://badgen.org/img/zenn/long910/likes?style=flat-square)](https://zenn.dev/long910)
[![Followers](https://badgen.org/img/zenn/long910/followers?style=flat-square)](https://zenn.dev/long910)
[![Articles](https://badgen.org/img/zenn/long910/articles?style=flat-square)](https://zenn.dev/long910)

[Zenn](https://zenn.dev/long910) に公開している技術記事のソースリポジトリです。
`main` ブランチへの push をトリガーに、複数プラットフォームへ自動同期します。

---

## 同期プラットフォーム一覧

| プラットフォーム | 対象読者 | 翻訳 | 認証方式 | 自動化 |
|---|---|---|---|---|
| [GitHub Pages](https://long-910.github.io) | 日本語 | なし | GH_PAT | GitHub Actions |
| [Qiita](https://qiita.com) | 日本語 | なし | API Token | GitHub Actions |
| はてなブログ | 日本語 | なし | API Key | GitHub Actions |
| 微信公众号 (WeChat) | 中国語 | DeepL (日→中) | AppID/Secret | GitHub Actions |
| 知乎 (Zhihu) | 中国語 | DeepL (日→中) | Cookie (ローカル) | ローカル実行 |
| CSDN | 中国語 | DeepL (日→中) | Cookie (ローカル) | ローカル実行 |

---

## 記事の書き方

### ファイル命名規則

```
articles/YYYY-MM-DD-slug.md
```

### フロントマター

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

### ローカルプレビュー

```bash
npm install
npx zenn preview   # http://localhost:8000 でプレビュー
```

---

## 各プラットフォームのセットアップ

### 共通: GitHub Secrets の設定

リポジトリの **Settings → Secrets and variables → Actions** で以下を設定します。

| Secret 名 | 用途 |
|---|---|
| `GH_PAT` | GitHub Pages 同期用 PAT（`repo` スコープ） |
| `QIITA_TOKEN` | Qiita API トークン |
| `HATENA_ID` | はてな ID |
| `HATENA_BLOG_ID` | はてなブログ ID（例: long910.hatenablog.com） |
| `HATENA_API_KEY` | はてなブログ API キー |
| `DEEPL_API_KEY` | DeepL API キー（中国語翻訳用・月50万文字無料） |
| `WECHAT_APP_ID` | 微信公众号 AppID |
| `WECHAT_APP_SECRET` | 微信公众号 AppSecret |
| `WECHAT_THUMB_MEDIA_ID` | 記事カバー画像の永久素材 media_id |

### DeepL API キーの取得

1. [deepl.com/en/pro#developer](https://www.deepl.com/en/pro#developer) で無料アカウント作成
2. クレジットカード不要・月50万文字無料
3. APIキーを `DEEPL_API_KEY` に設定

### 微信公众号 (WeChat) のセットアップ

1. [微信公众平台](https://mp.weixin.qq.com/) でAppID・AppSecretを取得
2. 記事カバー画像を永久素材としてアップロードし `media_id` を取得
3. GitHub Secrets に上記3つを設定

---

## 知乎 (Zhihu) / CSDN のセットアップ（ローカル実行）

知乎・CSDNは公式APIがないため、Seleniumによるブラウザ自動化を使用します。
**ローカル環境での実行専用**です（GitHub Actionsでは動作しません）。

### 必要なもの

- Python 3.11+
- Google Chrome
- `DEEPL_API_KEY` 環境変数

```bash
pip install -r scripts/requirements.txt
```

### 初回セットアップ（ログイン情報の保存）

```bash
# 知乎
python scripts/post-to-zhihu.py --setup

# CSDN
python scripts/post-to-csdn.py --setup
```

ブラウザが開くので、手動でログインして Enter を押してください。
Cookieが `scripts/zhihu-cookies.json` / `scripts/csdn-cookies.json` に保存されます（`.gitignore` 済み）。

---

## 記事の投稿

### GitHub Actions（自動）

`main` ブランチに push すると、変更された記事が各プラットフォームに自動投稿されます。

```
git push origin main
```

手動実行（GitHub Actions タブから workflow_dispatch）も可能です。

### ローカル実行（知乎・CSDN、およびその他プラットフォーム）

> **注意:** 投稿追跡ファイル (`scripts/*-posted.json`) は `tracking-data` ブランチで管理されています。
> ローカル実行の前後に以下のコマンドで同期してください。

```bash
# 実行前: 最新の追跡データを取得
./scripts/fetch-tracking.sh

# 特定の記事を投稿
python scripts/post-to-zhihu.py articles/2026-03-15-my-article.md
python scripts/post-to-csdn.py articles/2026-03-15-my-article.md

# 未投稿の全記事を投稿
python scripts/post-to-zhihu.py --all
python scripts/post-to-csdn.py --all

# 翻訳のみ確認（実際には投稿しない）
python scripts/post-to-zhihu.py --dry-run articles/my-article.md
python scripts/post-to-csdn.py --dry-run articles/my-article.md

# ブラウザを表示してデバッグ
python scripts/post-to-zhihu.py --no-headless articles/my-article.md
python scripts/post-to-csdn.py --no-headless articles/my-article.md

# 投稿済み記事の一覧
python scripts/post-to-zhihu.py --list
python scripts/post-to-csdn.py --list

# 実行後: 更新した追跡データを保存
./scripts/push-tracking.sh
```

### WeChat（GitHub Actions または ローカル）

```bash
# ローカルで実行する場合（環境変数を設定して）
export DEEPL_API_KEY=...
export WECHAT_APP_ID=...
export WECHAT_APP_SECRET=...
export WECHAT_THUMB_MEDIA_ID=...

python scripts/post-to-wechat.py articles/2026-03-15-my-article.md

# 公開申請まで実行（デフォルトは草稿箱に保存のみ）
python scripts/post-to-wechat.py --publish articles/my-article.md
```

---

## プラットフォームの有効/無効切り替え

`.github/sync-platforms.json` で各プラットフォームの有効/無効を制御できます。

```json
{
  "platforms": {
    "github_pages": { "enabled": true, "exclude_articles": [] },
    "qiita":        { "enabled": true, "exclude_articles": [] },
    "hatena":       { "enabled": true, "exclude_articles": [] },
    "wechat":       { "enabled": true, "exclude_articles": [] },
    "csdn":         { "enabled": true, "exclude_articles": [] },
    "zhihu":        { "enabled": false, "exclude_articles": [] }
  }
}
```

特定の記事を除外するには `exclude_articles` に追加します：

```json
"exclude_articles": ["2025-06-06-yazi.md"]
```

---

## ディレクトリ構成

```
.
├── articles/                    # Zenn 記事
├── .github/
│   ├── sync-platforms.json      # プラットフォーム設定
│   └── workflows/
│       ├── sync-articles.yml    # GitHub Pages 同期
│       ├── auto-post-qiita.yml  # Qiita 自動投稿
│       ├── auto-post-hatena.yml # はてな 自動投稿
│       ├── auto-post-note.yml   # note 自動投稿
│       ├── auto-post-wechat.yml # WeChat 自動投稿
│       └── manual-sync.yml      # 手動同期（workflow_dispatch）
└── scripts/
    ├── requirements.txt
    ├── post-to-qiita.py
    ├── post-to-hatena.py
    ├── post-to-note.py
    ├── post-to-wechat.py        # WeChat（公式API + DeepL翻訳）
    ├── post-to-zhihu.py         # 知乎（Selenium + DeepL翻訳）
    ├── post-to-csdn.py          # CSDN（Selenium + DeepL翻訳）
    ├── fetch-tracking.sh        # 追跡データをローカルに取得
    └── push-tracking.sh         # 追跡データをリモートに保存
```

> **追跡ファイル (`*-posted.json`) について**
> `main` ブランチには含まれず、`tracking-data` ブランチで管理されています。
> GitHub Actions は自動で同期します。ローカル実行時は `fetch-tracking.sh` / `push-tracking.sh` を使用してください。

---

## ライセンス

MIT License
