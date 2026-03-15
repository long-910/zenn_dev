---
title: "Zenn記事をはてなブログに自動同期投稿する仕組みを作った【AtomPub API活用】"
emoji: "🔵"
type: "tech"
topics: ["hatenablog", "githubactions", "python", "automation", "zenn"]
published: false
published_at: "2026-03-15 14:00"
---

:::message
この記事は **Claude Code**（claude.ai/code）を使用して作成しました。
:::

## はじめに

[Qiita自動同期](https://zenn.dev/long910/articles/2026-03-15-qiita-auto-posting) に続いて、今回は **はてなブログへの自動投稿** を追加しました。

はてなブログは国内最大級のブログプラットフォームで、技術系だけでなく幅広い読者層にリーチできます。また、はてなブックマークとの連携で技術記事がバズりやすいのも魅力です。

---

## はてなブログ AtomPub API の特徴

はてなブログは **AtomPub**（Atom Publishing Protocol）という標準プロトコルでAPIを公開しています。

| 項目 | 内容 |
|------|------|
| プロトコル | AtomPub (RFC 5023) |
| 認証 | Basic認証（はてなID + APIキー） |
| コンテンツ形式 | Markdown / HTML / はてな記法 |
| エンドポイント | `https://blog.hatena.ne.jp/{id}/{blog}/atom/entry` |
| 記事作成 | `POST` |
| 記事更新 | `PUT` |

### QiitaやZhihuとの違い

| | Qiita | はてなブログ | 知乎 |
|--|-------|------------|------|
| API種別 | 公式REST | 公式AtomPub | 非公式 |
| 認証 | Bearer Token | Basic認証 | Cookie |
| 外部ライブラリ | requests | 標準ライブラリのみ ✅ | requests |
| コンテンツ | Markdown | Markdown/HTML | HTML |

はてなブログはPythonの標準ライブラリだけで実装できるのが強みです。

---

## セットアップ

### 1. APIキーの取得

1. [はてなブログの詳細設定](https://blog.hatena.ne.jp/my/config/detail) にアクセス
2. ページ下部の「APIキー」をコピー

### 2. ブログIDの確認

ブログIDはブログのURLから確認できます：

- `https://long910.hatenablog.com/` → ブログID: `long910.hatenablog.com`
- `https://long910.hateblo.jp/` → ブログID: `long910.hateblo.jp`

### 3. GitHub Secretsに追加

**Settings → Secrets and variables → Actions → Secrets** に追加：

| Secret名 | 値 |
|----------|-----|
| `HATENA_ID` | はてなID（例: `long910`） |
| `HATENA_BLOG_ID` | ブログID（例: `long910.hatenablog.com`） |
| `HATENA_API_KEY` | 詳細設定ページで取得したAPIキー |

### 4. 自動投稿の有効化

**Settings → Secrets and variables → Actions → Variables** に追加：

| Variable名 | 値 |
|-----------|-----|
| `HATENA_AUTO_POST` | `true` |

---

## 実装のポイント

### AtomPub XML の組み立て

Atom形式のXMLをPython標準の `xml.etree.ElementTree` で生成しています：

```python
def build_atom_entry(title, content, categories, draft=False):
    entry = ET.Element("{http://www.w3.org/2005/Atom}entry")

    # タイトル
    title_el = ET.SubElement(entry, "{http://www.w3.org/2005/Atom}title")
    title_el.text = title

    # 本文（Markdownとして指定）
    content_el = ET.SubElement(entry, "{http://www.w3.org/2005/Atom}content")
    content_el.set("type", "text/x-markdown")
    content_el.text = content

    # カテゴリ（Zennのtopicsがそのまま使える）
    for cat in categories:
        cat_el = ET.SubElement(entry, "{http://www.w3.org/2005/Atom}category")
        cat_el.set("term", cat)

    # 下書き設定
    control = ET.SubElement(entry, "{http://www.w3.org/2007/app}control")
    draft_el = ET.SubElement(control, "{http://www.w3.org/2007/app}draft")
    draft_el.text = "yes" if draft else "no"

    return ET.tostring(entry, ...)
```

### Zenn記法 → はてなブログ変換

| Zenn | はてなブログ |
|------|------------|
| `:::message` | `> 💡 blockquote` |
| `:::message alert` | `> ⚠️ blockquote` |
| `:::details タイトル` | `<details><summary>タイトル</summary>` |
| `@[youtube](id)` | YouTube URL |

---

## 手動投稿の使い方

```bash
export HATENA_ID="your-hatena-id"
export HATENA_BLOG_ID="your-blog.hatenablog.com"
export HATENA_API_KEY="your-api-key"

# 特定の記事を投稿
python scripts/post-to-hatena.py articles/2026-03-08-vibe-coding.md

# 未投稿の全記事を投稿
python scripts/post-to-hatena.py --all

# 変換内容を確認（投稿しない）
python scripts/post-to-hatena.py --dry-run articles/my-article.md

# 下書きとして保存
python scripts/post-to-hatena.py --draft articles/my-article.md

# 既存記事を更新
python scripts/post-to-hatena.py --force articles/my-article.md

# 投稿済み一覧を確認
python scripts/post-to-hatena.py --list
```

---

## 現在の全体構成

これで1回のpushで4つのプラットフォームに自動配信されます：

```
main へ push
    ↓
┌─────────────────────────────────────────────┐
│ GitHub Actions                               │
│                                             │
│  sync-articles.yml → GitHub Pages           │
│  auto-post-qiita.yml → Qiita (日本語)       │
│  auto-post-hatena.yml → はてなブログ (日本語) │  ← 今回追加
│  auto-post-zhihu.yml → 知乎 (中国語翻訳)    │
└─────────────────────────────────────────────┘
```

### 必要なSecretsまとめ

| Secret | 用途 |
|--------|------|
| `GH_PAT` | GitHub Pages同期 |
| `QIITA_TOKEN` | Qiita投稿 |
| `HATENA_ID` | はてなブログ投稿 |
| `HATENA_BLOG_ID` | はてなブログ投稿 |
| `HATENA_API_KEY` | はてなブログ投稿 |
| `ZHIHU_COOKIE` | 知乎投稿 |
| `ANTHROPIC_API_KEY` | 知乎投稿（翻訳用） |

### 必要なVariablesまとめ

| Variable | 値 | 用途 |
|----------|-----|------|
| `QIITA_AUTO_POST` | `true` | Qiita自動投稿の有効化 |
| `HATENA_AUTO_POST` | `true` | はてな自動投稿の有効化 |
| `ZHIHU_AUTO_POST` | `true` | 知乎自動投稿の有効化 |

---

## まとめ

はてなブログはAtomPub APIが公式で提供されており、Python標準ライブラリだけで実装できるシンプルさが魅力です。Qiitaとは異なる読者層（一般ブロガー・はてなブックマーカー）にもリーチできるため、クロスポストの効果が高いプラットフォームです。

次の拡張候補としては **Dev.to**（英語圏）や **Hashnode** があります。どちらも公式REST/GraphQL APIを持ち、Claude APIで英訳すれば海外エンジニアへのリーチも実現できます。

---

## 参考リンク

- [はてなブログ AtomPub API ドキュメント](https://developer.hatena.ne.jp/ja/documents/blog/apis/atom)
- [AtomPub (RFC 5023)](https://tools.ietf.org/html/rfc5023)
- [はてなブログ APIキー設定](https://blog.hatena.ne.jp/my/config/detail)
