---
title: "Zenn記事をQiitaに自動で同期投稿する仕組みを作った【技術ブログ多プラットフォーム戦略】"
emoji: "📡"
type: "tech"
topics: ["qiita", "githubactions", "python", "automation", "zenn"]
published: true
published_at: "2026-03-15 13:00"
---

:::message
この記事は **Claude Code**（claude.ai/code）を使用して作成しました。
:::

## はじめに

前回の記事で [ZennからZhihu（知乎）への自動投稿](https://zenn.dev/long910/articles/2026-03-15-zhihu-auto-posting) の仕組みを作りました。

今回はさらに **Qiita への自動同期投稿** を追加しました。Zennで記事を書いてGitHubにpushするだけで、Qiitaにも自動で同じ内容が投稿されます。

---

## 技術ブログプラットフォーム比較

まず、日本の技術者が使える主なプラットフォームを整理します。

### 主要プラットフォーム比較表

| プラットフォーム | 言語 | 公式API | 自動化難易度 | 主な読者層 |
|----------------|------|---------|------------|-----------|
| **Zenn** | 日本語 | CLI/REST | ★☆☆ 簡単 | 日本人エンジニア |
| **Qiita** | 日本語 | REST v2 ✅ | ★☆☆ 簡単 | 日本人エンジニア（最大手） |
| **Hatena Blog** | 日本語 | AtomPub ✅ | ★★☆ 中程度 | 日本語ブロガー全般 |
| **Dev.to** | 英語 | REST ✅ | ★☆☆ 簡単 | 海外エンジニア |
| **Hashnode** | 英語 | GraphQL ✅ | ★★☆ 中程度 | 海外エンジニア |
| **Medium** | 英語 | ❌ なし | 対応不可 | 一般・ビジネス層 |
| **Note** | 日本語 | ❌ なし | 対応不可 | 一般向け日本語 |
| **知乎 (Zhihu)** | 中国語 | 非公式のみ | ★★★ 難しい | 中国語圏エンジニア |

### なぜQiitaへのクロスポストが有効か

- **Qiitaのユーザー数は国内最大規模**: 日本の技術系プラットフォームで最も多くのアクティブユーザーを持つ
- **検索流入が多い**: Qiitaの記事はGoogle検索で上位に出やすい
- **コミュニティが活発**: LGTM（いいね相当）やコメントで反応を得やすい
- **ZennとQiitaはターゲットが重なる**: 同じ日本語エンジニア向けで、読者の取りこぼしを防げる

---

## 全体構成

今回の構成はZhihu連携と合わせると以下のようになります：

```
Zenn記事 (articles/*.md)
    │
    ▼  git push to main
GitHub Actions
    │
    ├── [sync-articles.yml]
    │       └── GitHub Pages (long-910.github.io) へ同期
    │
    ├── [auto-post-qiita.yml]  ← 今回追加
    │       └── Qiita API v2 → 日本語のまま投稿
    │
    └── [auto-post-zhihu.yml]  ← 前回追加
            └── Claude API (翻訳) → 知乎 (非公式API) → 中国語で投稿
```

---

## Qiita連携の実装

### ZhihuとQiitaの違い

| 項目 | Qiita | 知乎 (Zhihu) |
|------|-------|-------------|
| API | 公式 REST API v2 | 非公式API |
| 認証 | Bearer Token | Cookie |
| 言語 | 日本語のまま ✅ | 中国語に翻訳が必要 |
| コンテンツ形式 | Markdown ✅ | HTML |
| 安定性 | 高い ✅ | 低い（変更リスクあり） |

### セットアップ

#### 1. Qiitaアクセストークンの取得

1. [Qiita設定ページ](https://qiita.com/settings/applications) にアクセス
2. 「個人用アクセストークン」→「新しいトークンを発行する」
3. スコープ: **`read_qiita`** と **`write_qiita`** にチェック
4. 発行されたトークンをコピー（再表示されないので注意）

#### 2. GitHub Secretsに追加

リポジトリの **Settings → Secrets and variables → Actions → Secrets** に追加：

| Secret名 | 値 |
|----------|-----|
| `QIITA_TOKEN` | Qiitaで発行したアクセストークン |

#### 3. GitHub Variablesで自動投稿を有効化

**Settings → Secrets and variables → Actions → Variables** に追加：

| Variable名 | 値 |
|-----------|-----|
| `QIITA_AUTO_POST` | `true` |

これで `main` へのpush時に自動で Qiita に投稿されます。

---

### Zenn記法 → Qiita記法の変換

Zenn固有の記法をQiita互換に変換します：

| Zenn記法 | Qiita記法 |
|---------|----------|
| `:::message` | `:::note info` |
| `:::message alert` | `:::note alert` |
| `:::details タイトル` | `<details><summary>タイトル</summary>` |
| `@[youtube](id)` | YouTube URL に変換 |

```python
def convert_zenn_to_qiita(content: str) -> str:
    # :::message → :::note info
    content = re.sub(r":::message\n", ":::note info\n", content)

    # :::message alert → :::note alert
    content = re.sub(r":::message alert\n", ":::note alert\n", content)

    # :::details → <details><summary>...</summary>
    def replace_details(m):
        title = m.group(1).strip()
        body = m.group(2).strip()
        return f"<details><summary>{title}</summary>\n\n{body}\n\n</details>"

    content = re.sub(
        r":::details\s+(.*?)\n(.*?):::",
        replace_details,
        content,
        flags=re.DOTALL
    )
    return content
```

### Qiita APIへの投稿

Qiitaの公式APIは非常に使いやすく、Markdownをそのまま投稿できます：

```python
class QiitaClient:
    def create_item(self, title: str, body: str, tags: list) -> dict:
        resp = self.session.post(
            "https://qiita.com/api/v2/items",
            json={
                "title": title,
                "body": body,  # Markdownのまま！
                "tags": tags,  # [{"name": "Python", "versions": []}]
                "private": False,
                "coediting": False,
            }
        )
        return resp.json()
```

ZennのfrontmatterにあるTopicsをそのままQiitaのTagsに使えるのもポイントです：

```python
# Zennのfrontmatter
topics: ["python", "githubactions", "automation"]

# → Qiita APIに送るタグ
tags = [{"name": "python", "versions": []}, ...]
```

---

## 手動投稿の使い方

```bash
# 環境変数を設定
export QIITA_TOKEN="your-qiita-token"

# 特定の記事を投稿
python scripts/post-to-qiita.py articles/2026-03-08-vibe-coding.md

# 全未投稿記事を一括投稿
python scripts/post-to-qiita.py --all

# 変換内容を確認してから投稿（ドライラン）
python scripts/post-to-qiita.py --dry-run articles/my-article.md

# 既存記事を更新（--force で再投稿）
python scripts/post-to-qiita.py --force articles/my-article.md

# 限定公開で投稿
python scripts/post-to-qiita.py --private articles/my-article.md

# 投稿済み一覧を確認
python scripts/post-to-qiita.py --list
```

---

## 投稿履歴の管理

`scripts/qiita-posted.json` で投稿履歴を追跡します：

```json
{
  "2026-03-08-vibe-coding.md": {
    "url": "https://qiita.com/long910/items/xxxxxxxxxxxxxxxx",
    "item_id": "xxxxxxxxxxxxxxxx",
    "title": "Vibe Coding完全ガイド",
    "posted_at": "2026-03-15T12:00:00Z",
    "updated_at": "2026-03-15T12:00:00Z"
  }
}
```

このファイルはGitHub Actionsが自動でコミットするため、チーム間での投稿状態の共有も簡単です。

---

## Qiitaの同一コンテンツポリシーについて

:::message alert
Qiitaは重複コンテンツに関するポリシーを持っています。Zennと同じ内容を投稿する場合は、記事末尾にZennへのクロスリンクを追記することで「重複コンテンツ」ではなく「転載・参照」として扱われます。このスクリプトは自動的にZennへのリンクを追記します。
:::

スクリプトが自動追記する内容：

```markdown
---

> この記事は[Zenn](https://zenn.dev/long910/articles/slug)でも公開しています。
```

---

## まとめ：今回の構成全体

現在のリポジトリでは、1回のpushで以下のプラットフォームすべてに自動配信されます：

```
main へ push
    ↓
1. GitHub Pages (long-910.github.io)  ← 元から設定済み
2. Qiita                               ← 今回追加（日本語）
3. 知乎 (Zhihu)                        ← 前回追加（中国語翻訳）
```

### 各プラットフォームのセットアップ概要

| 手順 | GitHub Pages | Qiita | 知乎 |
|------|-------------|-------|------|
| Secret追加 | `GH_PAT` | `QIITA_TOKEN` | `ZHIHU_COOKIE`, `ANTHROPIC_API_KEY` |
| Variable追加 | なし | `QIITA_AUTO_POST=true` | `ZHIHU_AUTO_POST=true` |
| 更新頻度 | Cookieは不要 | トークンは長期有効 | Cookieは数週間で失効 |

---

## 今後の拡張アイデア

今後さらに追加できるプラットフォーム：

- **Dev.to**: 英語圏向け。公式REST API対応。Zhihu同様Claude APIで英訳して投稿可能
- **Hashnode**: GraphQL APIで投稿可能。独自ドメインも設定できる
- **はてなブログ**: AtomPub APIで投稿可能。日本語圏の幅広い読者へリーチ

---

## 参考リンク

- [Qiita API v2 ドキュメント](https://qiita.com/api/v2/docs)
- [Qiita アクセストークン発行](https://qiita.com/settings/applications)
- [Zenn から 知乎(Zhihu) 自動投稿の記事](https://zenn.dev/long910/articles/2026-03-15-zhihu-auto-posting)
