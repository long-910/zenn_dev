---
title: "Zenn記事をQiita・はてな・noteに自動同期する仕組みを作った【マルチプラットフォーム配信】"
emoji: "🌐"
type: "tech"
topics: ["zenn", "qiita", "hatenablog", "githubactions", "automation"]
published: true
published_at: "2026-03-15 16:00"
---

:::message
この記事は **Claude Code**（claude.ai/code）を使用して作成しました。
:::

## はじめに

技術記事を書く労力は変わらないのに、公開先が1つだけではもったいない。そう思ってZennで書いた記事を複数のプラットフォームに自動配信する仕組みを構築しました。

この記事は、各プラットフォームのAPI調査から実装まで、全プロセスを記録したものです。

:::message
**検証状況について**
- **GitHub Pages・Qiita・はてなブログ・note.com**: 実装済み・順次検証中
- **知乎（Zhihu）**: 構想段階・現時点では未検証（詳細は後述）
:::

---

## 各プラットフォームのAPI調査結果

まず、候補となるプラットフォームのAPI対応状況を調べました。

### 調査対象と結論

| プラットフォーム | 公式API | 方式 | 実装難易度 | 安定性 |
|----------------|:-------:|------|:--------:|:------:|
| **GitHub Pages** | ✅ | Git push / GH API | ★☆☆ | 高 |
| **Qiita** | ✅ | REST API v2 | ★☆☆ | 高 |
| **はてなブログ** | ✅ | AtomPub (RFC 5023) | ★☆☆ | 高 |
| **Dev.to** | ✅ | REST API | ★☆☆ | 高 |
| **Hashnode** | ✅ | GraphQL API | ★★☆ | 高 |
| **note.com** | ❌ | 非公式（内部API） | ★★☆ | 低〜中 |
| **知乎 (Zhihu)** | ❌ | 非公式（Cookie認証） | ★★★ | 低 |
| **Medium** | ❌ | なし（import機能のみ） | 対応不可 | — |

### ポイント解説

**Qiita・はてなブログ**: 公式APIが整備されており、最も安定した選択肢。Qiitaはアクセストークン1つで済み、はてなはAtomPubという標準プロトコルを使うため実装が堅牢。順次動作検証を進めています。

**Dev.to・Hashnode**: 英語圏向け。公式APIあり。Claude APIで英訳すれば自動化可能。（今回は未実装）

**note.com**: **公式APIなし**。しかしコミュニティが内部APIを解析しており、Pythonライブラリ（NoteClient）や直接API呼び出しで自動投稿が可能。ただし仕様変更のリスクあり。実装済みで検証中。

**知乎（Zhihu）**: 中国最大の知識共有プラットフォーム（月間アクティブユーザー1億人超）。公式API完全非公開。Cookie認証で投稿可能だが、Cookieの有効期限切れや仕様変更リスクが高い。また日本語記事をそのまま投稿しても意味がないため、Claude APIによる中国語翻訳が必須。**現時点では構想段階にとどめており、未検証です。**

**Medium**: 2024年以降、記事投稿APIを完全廃止。技術的な自動投稿は不可能。

---

## note.com の内部API詳細調査

note.comに対しては追加で詳しく調査しました。

### 現時点での状況（2026年3月）

note.comは一切の公式APIドキュメントを公開していません。しかし、日本のエンジニアコミュニティが内部APIをリバースエンジニアリングした記録が複数存在します。

### 自動投稿の2つのアプローチ

#### アプローチ1：直接HTTP API（今回採用）

コミュニティが解析した内部REST APIを直接呼び出す方法です。

```
# ログイン
POST https://note.com/api/v1/sessions
Body: {"login": "email", "password": "password"}
→ セッションCookie (_note_session_v5) が発行される

# 記事作成（下書き or 公開）
POST https://note.com/api/v1/text_notes
Body: {
  "name": "タイトル",
  "body": "Markdownテキスト",
  "hashtag_notes_attributes": [{"name": "タグ"}],
  "status": "draft" or "published"
}

# 記事更新（公開状態変更など）
PATCH https://note.com/api/v1/text_notes/{id}
Body: {"status": "published"}
```

**メリット**: 軽量・高速・ブラウザ不要・GitHub Actionsとの相性が良い
**デメリット**: APIエンドポイント変更で突然壊れる可能性がある

#### アプローチ2：NoteClient（Seleniumブラウザ自動化）

`pip install NoteClient` でインストールできるコミュニティ製ライブラリ（MIT）です。

```python
from note_client import Note

note = Note(
    email="your@email.com",
    password="your_password",
    user_id="12345"  # 数値のユーザーID
)

result = note.create_article(
    title="記事タイトル",
    content_body="## Markdown本文...",
    input_tag_list=["python", "automation"],
    post_setting=True,   # True=即時公開, False=下書き
    headless=True,
)
```

**メリット**: UI変更に対してHTTPより修復しやすい
**デメリット**: Chrome/Firefoxが必要。GitHub Actionsでは追加インストールが必要。処理が遅くリソース消費が大きい

**今回はアプローチ1（直接HTTP）を採用**しました。GitHub Actionsでブラウザなしに動き、requirements.txtへの追加依存も不要なためです。

---

## 全体アーキテクチャ

```
articles/*.md (Zenn記事)
     │
     └─ git push to main
              │
              ▼
     GitHub Actions (同時並行で実行)
              │
    ┌─────────┼────────────┬────────────┐
    ▼         ▼            ▼            ▼
GitHub     Qiita       はてな        note.com
Pages    REST API    AtomPub     内部API(非公式)
(日本語)   (日本語)    (日本語)      (日本語)
                                  ※順次検証中

    ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄
    知乎（Zhihu）: 構想段階・未検証
    ※ 実現には中国語翻訳(Claude API)が必要
```

### 設定ファイル構成

```
.github/
├── sync-platforms.json   ← 同期先の有効/無効・除外記事を一元管理
└── workflows/
    ├── sync-articles.yml       → GitHub Pages
    ├── auto-post-qiita.yml     → Qiita
    ├── auto-post-hatena.yml    → はてなブログ
    └── auto-post-note.yml      → note.com
scripts/
├── post-to-qiita.py
├── post-to-hatena.py
├── post-to-note.py
├── requirements.txt
├── qiita-posted.json     ← 各プラットフォームの投稿履歴
├── hatena-posted.json
└── note-posted.json
```

---

## 設定ファイル `.github/sync-platforms.json`

このファイル1つで全プラットフォームの同期先を制御します：

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

`enabled: true` に変更してpushするだけで自動投稿が始まります。

---

## 各プラットフォームのセットアップ

### GitHub Secrets 一覧

| Secret名 | 対象 | 取得方法 |
|----------|------|---------|
| `GH_PAT` | GitHub Pages | GitHub → Settings → Developer settings → PAT |
| `QIITA_TOKEN` | Qiita | https://qiita.com/settings/applications |
| `HATENA_ID` | はてなブログ | はてなID（例: `long910`） |
| `HATENA_BLOG_ID` | はてなブログ | ブログURL（例: `long910.hatenablog.com`） |
| `HATENA_API_KEY` | はてなブログ | https://blog.hatena.ne.jp/my/config/detail |
| `NOTE_EMAIL` | note.com | note.comログインメール |
| `NOTE_PASSWORD` | note.com | note.comログインパスワード |
| `NOTE_USER_ID` | note.com | note.comのユーザーID（URLのID） |

:::message alert
パスワードや認証情報はGitHub Secretsに保存し、絶対にコードにハードコードしないでください。
:::

---

## Zenn記法の変換対応表

各プラットフォームへの変換はスクリプトが自動処理します：

| Zenn記法 | Qiita | はてなブログ | note.com |
|---------|-------|------------|---------|
| `:::message` | `:::note info` | `> 💡 blockquote` | `**💡 メモ:**` |
| `:::message alert` | `:::note alert` | `> ⚠️ blockquote` | `**⚠️ 注意:**` |
| `:::details タイトル` | `<details>` HTML | `<details>` HTML | **タイトル**（展開） |
| `@[youtube](id)` | YouTube URL | YouTube URL | YouTube URL |

---

## 手動投稿コマンド

```bash
# 環境変数を設定（例: Qiita）
export QIITA_TOKEN="your-token"

# ドライランで変換内容を確認
python scripts/post-to-qiita.py --dry-run articles/2026-03-08-vibe-coding.md

# 特定記事を投稿
python scripts/post-to-qiita.py articles/2026-03-08-vibe-coding.md

# 未投稿の全記事を一括投稿
python scripts/post-to-qiita.py --all

# 投稿済み記事を更新
python scripts/post-to-qiita.py --force articles/my-article.md

# note.com（非公式API）
export NOTE_EMAIL="you@example.com"
export NOTE_PASSWORD="your-password"
export NOTE_USER_ID="your-note-id"
python scripts/post-to-note.py --dry-run articles/my-article.md
```

---

## 安定性とリスクの整理

### 公式API（推奨）: Qiita・はてなブログ

最も安定。アクセストークンは長期有効で、API仕様の破壊的変更は公式アナウンスされます。順次動作確認を進めています。

### 非公式API（リスクあり）: note.com

| リスク | note.com |
|--------|---------|
| API仕様変更 | 中（定期的に変わる） |
| 認証の失効 | 低（パスワードは長期有効） |
| アカウントBANリスク | 低（自動投稿の明示禁止なし） |
| 対処法 | エラー時に手動確認 |

非公式APIを使うプラットフォームは `enabled: false` をデフォルトにして、意識的に有効化する設計にしています。

### 構想段階: 知乎（Zhihu）

知乎への投稿はアイデアとして検討しているものの、現時点では**未検証**です。実現するには非公式のCookie認証に加えてClaude APIによる中国語翻訳が必要で、実用化のハードルが高い状況です。興味のある方は [構想設計メモ](https://zenn.dev/long910/articles/2026-03-15-zhihu-auto-posting) を参照してください。

---

## まとめ

| | 実装 | 検証状況 | 安定性 |
|--|:---:|:------:|:------:|
| GitHub Pages | ✅ | 稼働中 | ◎ |
| Qiita | ✅ | 検証中 | ◎ |
| はてなブログ | ✅ | 検証中 | ◎ |
| note.com | ✅ | 検証中 | △（非公式） |
| 知乎（Zhihu） | 🔧 | 構想段階・未検証 | —（非公式） |

**1回のgit pushで最大4プラットフォームに配信**できるようになりました（Zhihuは今後の検討課題）。

---

## シリーズ記事

1. [Qiita自動同期投稿](https://zenn.dev/long910/articles/2026-03-15-qiita-auto-posting)
2. [はてなブログAtomPub自動投稿](https://zenn.dev/long910/articles/2026-03-15-hatena-auto-posting)
3. [sync-platforms.jsonで設定を一元管理](https://zenn.dev/long910/articles/2026-03-15-sync-platforms-config)
4. **この記事: 全プラットフォーム概要**
5. [知乎（Zhihu）自動投稿の構想設計メモ](https://zenn.dev/long910/articles/2026-03-15-zhihu-auto-posting)
