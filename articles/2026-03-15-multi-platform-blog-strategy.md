---
title: "Zenn記事をQiita・はてな・noteに自動同期する仕組みを作った"
emoji: "🚀"
type: "tech"
topics: ["zenn", "qiita", "hatenablog", "githubactions", "automation"]
published: true
published_at: "2026-03-15 16:00"
---

:::message
この記事は **Claude Code**（claude.ai/code）を使用して作成しました。
:::

## TL;DR

`git push` 1回で Zenn の記事を **Qiita・はてなブログ・note.com** に自動配信できる仕組みを作りました。設定ファイル（JSON）でどこに送るかをコードで管理できます。

```
git push → GitHub Actions → Qiita ✅
                          → はてなブログ ✅
                          → note.com ✅
                          → GitHub Pages ✅
```

---

## なぜマルチプラットフォームか

記事を書く手間は1回でも、読んでもらえる機会は増やせます。

| プラットフォーム | 強み |
|:---:|:---|
| **Zenn** | エンジニア特化。本・スクラップ機能が強力 |
| **Qiita** | 国内最大規模の技術コミュニティ。検索流入が多い |
| **はてなブログ** | はてブとの連携でバズりやすい。エンジニア以外にも届く |
| **note.com** | 読みやすいUI。クリエイター層・一般層にリーチ |
| **GitHub Pages** | 自前サイト。ポートフォリオとして機能 |

---

## 全体アーキテクチャ

```
┌─────────────────────────────────────────────────┐
│  articles/*.md  ──  git push to main             │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
          ┌────────────────────────┐
          │    GitHub Actions      │
          │  (並列で同時実行)      │
          └──┬──────┬──────┬──────┘
             │      │      │      │
             ▼      ▼      ▼      ▼
         GitHub   Qiita  はてな  note.com
          Pages  REST   AtomPub  内部API
        (日本語) (日本語)(日本語) (日本語)
```

各ワークフローは `.github/sync-platforms.json` の `enabled` フラグで個別にON/OFFできます。

---

## プラットフォーム別 API まとめ

| | GitHub Pages | Qiita | はてなブログ | note.com |
|:---:|:---:|:---:|:---:|:---:|
| **公式API** | ✅ | ✅ | ✅ | ❌ |
| **認証方式** | PAT | Bearer Token | Basic認証 | パスワード |
| **コンテンツ形式** | Markdown | Markdown | Markdown | Markdown |
| **安定性** | ◎ | ◎ | ◎ | △ |
| **実装難易度** | ★☆☆ | ★☆☆ | ★★☆ | ★★☆ |
| **検証状況** | 稼働中 | 検証中 | 検証中 | 検証中 |

:::message
**note.com について**
公式APIは非公開ですが、コミュニティが解析した内部APIで自動投稿が可能です。ただし仕様変更のリスクがあります。
:::

---

## ファイル構成

```
.github/
├── sync-platforms.json        ← 同期先をON/OFFする設定ファイル
└── workflows/
    ├── sync-articles.yml      → GitHub Pages
    ├── auto-post-qiita.yml    → Qiita
    ├── auto-post-hatena.yml   → はてなブログ
    └── auto-post-note.yml     → note.com

scripts/
├── post-to-qiita.py
├── post-to-hatena.py
├── post-to-note.py
├── requirements.txt
├── qiita-posted.json          ← 投稿済み記事の追跡（重複防止）
├── hatena-posted.json
└── note-posted.json
```

---

## 設定ファイル `sync-platforms.json`

リポジトリ内の **このファイル1つ** で全プラットフォームを制御します。

```json
{
  "platforms": {
    "github_pages": {
      "enabled": true,
      "exclude_articles": ["2025-06-06-yazi.md"]
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

| フィールド | 説明 |
|---|---|
| `enabled` | `true` にするだけで自動投稿開始 |
| `exclude_articles` | このプラットフォームだけ除外したい記事ファイル名 |

以前はGitHub Variablesで管理していたので「どこに投稿されているか」がリポジトリを見てもわからない問題がありました。このファイルに一元化することでgitで履歴管理できます。

---

## セットアップ手順

### Step 1 — GitHub Secrets を登録する

リポジトリの **Settings → Secrets and variables → Actions** で登録します。

| Secret名 | 対象 | 取得場所 |
|---|---|---|
| `GH_PAT` | GitHub Pages | Settings → Developer settings → PAT |
| `QIITA_TOKEN` | Qiita | https://qiita.com/settings/applications |
| `HATENA_ID` | はてなブログ | はてなID（例: `long910`） |
| `HATENA_BLOG_ID` | はてなブログ | ブログURL（例: `long910.hatenablog.com`） |
| `HATENA_API_KEY` | はてなブログ | https://blog.hatena.ne.jp/my/config/detail |
| `NOTE_EMAIL` | note.com | note.comのログインメール |
| `NOTE_PASSWORD` | note.com | note.comのログインパスワード |
| `NOTE_USER_ID` | note.com | note.comのユーザーID |

:::message alert
認証情報は **必ずGitHub Secrets** に登録してください。コードにハードコードしたりリポジトリにコミットしたりしないでください。
:::

### Step 2 — sync-platforms.json を更新する

投稿したいプラットフォームの `enabled` を `true` に変えてpushするだけです。

```json
"qiita": {
  "enabled": true  ← ここを変えてpush
}
```

これだけで次のpushから自動投稿が始まります。

---

## 各プラットフォームの実装詳細

### Qiita — 公式REST API v2

Qiitaは公式APIが整備されており最もシンプルに実装できます。**Markdownをそのまま送れる**のがポイントです。

```python
# Zennのfrontmatter → QiitaのAPI形式に変換
{
    "title": article.title,
    "body": markdown_content,   # Markdownのまま！
    "tags": [{"name": t} for t in article.topics],
    "private": False,
}
```

**Zenn記法 → Qiita記法 の変換対応:**

| Zenn | Qiita |
|---|---|
| `:::message` | `:::note info` |
| `:::message alert` | `:::note alert` |
| `:::details タイトル` | `<details><summary>タイトル</summary>` |
| `@[youtube](id)` | YouTube URL |

:::message
Qiitaは重複コンテンツポリシーがあります。スクリプトはZennへのクロスリンクを記事末尾に自動追記します。
:::

---

### はてなブログ — AtomPub (RFC 5023)

はてなブログは標準プロトコル **AtomPub** でAPIを公開しています。**Python標準ライブラリだけ**で実装できるシンプルさが魅力です。

```python
# AtomPub XML を標準ライブラリで構築
import xml.etree.ElementTree as ET

entry = ET.Element("{http://www.w3.org/2005/Atom}entry")
# タイトル、本文(Markdown)、カテゴリ(=Zennのtopics)を設定
# → POST https://blog.hatena.ne.jp/{id}/{blog}/atom/entry
```

**エンドポイント:**

| 操作 | メソッド | URL |
|---|---|---|
| 記事作成 | `POST` | `https://blog.hatena.ne.jp/{id}/{blog}/atom/entry` |
| 記事更新 | `PUT` | `https://blog.hatena.ne.jp/{id}/{blog}/atom/entry/{entry_id}` |

**Zenn記法 → はてなブログ の変換対応:**

| Zenn | はてなブログ |
|---|---|
| `:::message` | `> 💡 blockquote` |
| `:::message alert` | `> ⚠️ blockquote` |
| `:::details タイトル` | `<details><summary>タイトル</summary>` |
| `@[youtube](id)` | YouTube URL |

---

### note.com — 非公式内部API

note.comは公式APIを公開していませんが、コミュニティが解析した内部APIで自動投稿できます。

**投稿フロー:**

```
1. POST /api/v1/sessions
   → Cookie (_note_session_v5) を取得

2. POST /api/v1/text_notes
   → 記事を下書き作成

3. PATCH /api/v1/text_notes/{id}
   → status: "published" で公開
```

:::message alert
note.comの内部APIは仕様変更のリスクがあります。エラー時は手動で確認してください。`enabled: false` がデフォルトです。
:::

---

## 手動投稿コマンド

自動投稿だけでなく、CLIから手動で投稿・確認もできます。

```bash
# --- Qiita ---
export QIITA_TOKEN="your-token"

python scripts/post-to-qiita.py --dry-run articles/my-article.md  # 変換確認
python scripts/post-to-qiita.py articles/my-article.md            # 投稿
python scripts/post-to-qiita.py --all                              # 未投稿を全部投稿
python scripts/post-to-qiita.py --force articles/my-article.md    # 更新
python scripts/post-to-qiita.py --list                             # 投稿済み一覧

# --- はてなブログ ---
export HATENA_ID="your-id"
export HATENA_BLOG_ID="your-blog.hatenablog.com"
export HATENA_API_KEY="your-key"

python scripts/post-to-hatena.py --draft articles/my-article.md   # 下書き保存
python scripts/post-to-hatena.py articles/my-article.md           # 公開投稿

# --- note.com ---
export NOTE_EMAIL="you@example.com"
export NOTE_PASSWORD="your-password"
export NOTE_USER_ID="your-note-id"

python scripts/post-to-note.py --dry-run articles/my-article.md   # 変換確認
python scripts/post-to-note.py articles/my-article.md             # 投稿
```

---

## 投稿履歴の管理

各プラットフォームの投稿済み記事は JSON ファイルで追跡します。GitHub Actionsが自動でコミットするため、重複投稿を防げます。

```json
// scripts/qiita-posted.json（例）
{
  "2026-03-08-vibe-coding.md": {
    "url": "https://qiita.com/long910/items/xxxx",
    "item_id": "xxxx",
    "title": "Vibe Coding完全ガイド",
    "posted_at": "2026-03-15T12:00:00Z"
  }
}
```

---

## 安定性まとめ

```
◎ 安定        GitHub Pages / Qiita / はてなブログ
               公式API・長期有効トークン

△ リスクあり   note.com
               非公式API・仕様変更の可能性あり

🔧 構想段階    知乎（Zhihu）
               非公式Cookie認証＋中国語翻訳が必要・未検証
```

:::message
知乎（Zhihu）への投稿はアイデアとして検討中ですが、現時点では**未検証**です。実現には非公式のCookie認証（数週間で失効）とClaude APIによる中国語翻訳が必要で、ハードルが高い状況です。
:::

---

## まとめ

| | 実装 | 検証状況 | 安定性 | 難易度 |
|:---:|:---:|:---:|:---:|:---:|
| GitHub Pages | ✅ | 稼働中 | ◎ | ★☆☆ |
| Qiita | ✅ | 検証中 | ◎ | ★☆☆ |
| はてなブログ | ✅ | 検証中 | ◎ | ★★☆ |
| note.com | ✅ | 検証中 | △ | ★★☆ |
| 知乎（Zhihu）| 🔧 | 構想段階 | — | ★★★ |

`sync-platforms.json` の `enabled` を `true` にするだけで投稿先を追加できます。まず Qiita から試してみることをおすすめします。

---

## 参考リンク

- [Qiita API v2 ドキュメント](https://qiita.com/api/v2/docs)
- [はてなブログ AtomPub API](https://developer.hatena.ne.jp/ja/documents/blog/apis/atom)
- [GitHub Actions ドキュメント](https://docs.github.com/ja/actions)
