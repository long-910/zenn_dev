---
title: "【構想設計メモ】Zenn記事を中国語翻訳して知乎（Zhihu）に自動投稿する仕組みを考えた"
emoji: "🔧"
type: "tech"
topics: ["zhihu", "claudeapi", "githubactions", "python", "automation"]
published: true
published_at: "2026-03-15 12:00"
---

:::message
この記事は **Claude Code**（claude.ai/code）を使用して作成しました。
:::

:::message alert
**この記事は構想・設計段階のメモです**

知乎（Zhihu）への自動投稿は現時点では**未検証**です。知乎の非公式APIはCookie認証が必要でハードルが高く、実際に動作確認できていません。コードは設計として記録しているものであり、そのまま動作することを保証できません。実用化は今後の検討課題としています。

日本語圏のプラットフォーム（Qiita・はてなブログ・note.com）への自動同期については [こちらの記事](https://zenn.dev/long910/articles/2026-03-15-multi-platform-blog-strategy) をご覧ください。
:::

## はじめに

Zennで技術記事を書いていると、「これ中国語圏の人にも読んでほしいな」と思うことがあります。中国最大の知識共有プラットフォーム **知乎（Zhihu）** は月間アクティブユーザー数が1億人を超えており、技術記事の需要も非常に高いです。

しかし実現にあたっては複数のハードルがあります：

- 知乎の公式APIは非公開（Cookie認証で代替するが不安定）
- 日本語記事をそのまま投稿しても意味がないため Claude API による中国語翻訳が必須
- Cookie は数週間で失効するため定期的な更新が必要

本記事はこれらのハードルを承知のうえで、**どうすれば実現できるかを設計・検討した記録**です。

仕組みとして想定しているのは：

1. **新しいZenn記事をpushしたとき**、Claude APIで自動翻訳して知乎に投稿
2. **既存記事**をコマンド一つで手動投稿
3. **投稿履歴**をJSONで管理して重複投稿を防ぐ

---

## 全体アーキテクチャ

```
Zenn記事 (日本語)
    │
    ▼
GitHub Actions (push to main)
    │
    ├─ Claude API (翻訳: 日本語 → 中国語)
    │
    ├─ Markdown → HTML 変換
    │
    └─ 知乎 API (非公式) → 知乎に投稿
            │
            └─ zhihu-posted.json (投稿履歴を記録)
```

使用する主な技術：

| 技術 | 用途 |
|------|------|
| Claude API (claude-opus-4-6) | 日本語→中国語翻訳 |
| 知乎 非公式API | 記事の投稿 |
| GitHub Actions | 自動化パイプライン |
| Python (requests, python-frontmatter, Markdown) | 処理スクリプト |

---

## 事前準備

### 1. Anthropic API キーの取得

[Anthropic Console](https://console.anthropic.com/) でAPIキーを発行します。

### 2. 知乎のCookieを取得

知乎のAPIは非公式のため、ログイン済みのブラウザからCookieを取得する必要があります。

1. ブラウザで [zhihu.com](https://www.zhihu.com) にログイン
2. 開発者ツール（F12）を開く
3. **Application** → **Cookies** → `www.zhihu.com` を選択
4. 以下のCookieを全て含むCookie文字列をコピー：
   - `z_c0`（認証トークン）
   - `_xsrf`（CSRFトークン）

Cookie文字列のフォーマット:
```
z_c0=xxxxxxxx; _xsrf=xxxxxxxx; ...
```

:::message alert
Cookieは個人認証情報です。GitHubの公開リポジトリには絶対に直接コミットしないでください。必ずSecretsを使用してください。
:::

### 3. GitHub Secretsの設定

リポジトリの **Settings → Secrets and variables → Actions** で以下を設定：

| Secret名 | 内容 |
|----------|------|
| `ANTHROPIC_API_KEY` | Claude APIキー |
| `ZHIHU_COOKIE` | 知乎のCookie文字列 |

### 4. GitHub Variables の設定

自動投稿を有効にするため、**Variables**（Secretsではなく）に以下を設定：

| Variable名 | 値 |
|-----------|-----|
| `ZHIHU_AUTO_POST` | `true` |

これにより、自動投稿を一時停止したい場合は `false` に変更するだけでOKです。

---

## ファイル構成

今回追加したファイルは以下の通りです：

```
.
├── scripts/
│   ├── post-to-zhihu.py      # メインスクリプト
│   ├── requirements.txt       # Python依存パッケージ
│   └── zhihu-posted.json      # 投稿履歴（自動更新）
└── .github/
    └── workflows/
        └── auto-post-zhihu.yml  # GitHub Actionsワークフロー
```

---

## スクリプトの実装

### Pythonスクリプト (`scripts/post-to-zhihu.py`)

主要な処理フローを説明します。

#### 1. Zenn記法のクリーニング

Zenn固有の記法（`:::message`、`:::details` 等）は知乎では表示されないため、標準的なMarkdownに変換します。

```python
def clean_zenn_content(content: str) -> str:
    # :::message ブロックをBlockquoteに変換
    content = re.sub(
        r":::message\n(.*?):::",
        r"> 💡 **提示:** \1",
        content, flags=re.DOTALL
    )
    # :::details ブロックをセクションに変換
    content = re.sub(
        r":::details\s+(.*?)\n(.*?):::",
        r"**\1**\n\n\2",
        content, flags=re.DOTALL
    )
    return content
```

#### 2. Claude APIで翻訳

`claude-opus-4-6` を使用して高品質な翻訳を行います。プロンプトでコードブロックやURLは翻訳しないよう指示しています。

```python
def translate_to_chinese(title: str, content: str) -> tuple[str, str]:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}]
    )
    # レスポンスをパースしてタイトルと本文を返す
    ...
```

#### 3. 知乎APIへの投稿

知乎の非公式APIを使用して記事を投稿します。投稿フローは：

1. 下書き作成 (`POST /api/articles/drafts`)
2. タイトルと内容を更新 (`PATCH /api/articles/{id}`)
3. 公開 (`POST /api/articles/{id}/publish`)

```python
class ZhihuClient:
    def create_draft(self) -> int:
        resp = self.session.post(
            "https://zhuanlan.zhihu.com/api/articles/drafts",
            json={"delta_time": 0}
        )
        return resp.json()["id"]

    def update_draft(self, article_id: int, title: str, html_content: str):
        self.session.patch(
            f"https://zhuanlan.zhihu.com/api/articles/{article_id}",
            json={"title": title, "content": html_content, "delta_time": 0}
        )

    def publish(self, article_id: int) -> str:
        self.session.post(
            f"https://zhuanlan.zhihu.com/api/articles/{article_id}/publish",
            json={"disclaimer_type": "none", "disclaimer_status": "none"}
        )
        return f"https://zhuanlan.zhihu.com/p/{article_id}"
```

---

## GitHub Actions ワークフロー

`main` ブランチに `articles/*.md` への変更がpushされると自動実行されます。

```yaml
on:
  push:
    branches: [main]
    paths: ["articles/*.md"]

jobs:
  post-to-zhihu:
    if: ${{ vars.ZHIHU_AUTO_POST == 'true' }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 2

      - name: Find changed articles
        id: changed
        run: |
          CHANGED=$(git diff --name-only --diff-filter=ACM HEAD~1 HEAD -- 'articles/*.md' | tr '\n' ' ')
          echo "files=$CHANGED" >> "$GITHUB_OUTPUT"

      - name: Post articles to Zhihu
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          ZHIHU_COOKIE: ${{ secrets.ZHIHU_COOKIE }}
        run: |
          for file in ${{ steps.changed.outputs.files }}; do
            python scripts/post-to-zhihu.py "$file"
          done

      - name: Commit tracking file
        run: |
          git add scripts/zhihu-posted.json
          git diff --staged --quiet || git commit -m "chore: Update Zhihu posting tracking [skip ci]"
          git push origin main
```

---

## 手動投稿の使い方

### セットアップ

```bash
# 依存パッケージのインストール
pip install -r scripts/requirements.txt

# 環境変数の設定
export ANTHROPIC_API_KEY="your-api-key"
export ZHIHU_COOKIE="z_c0=xxx; _xsrf=xxx; ..."
```

### 特定記事を投稿

```bash
python scripts/post-to-zhihu.py articles/2026-03-08-vibe-coding.md
```

### 複数記事を一括投稿

```bash
python scripts/post-to-zhihu.py articles/2026-02-21-claude-code-usage-limit.md articles/2026-02-22-mcp-introduction.md
```

### 未投稿の全記事を投稿

```bash
python scripts/post-to-zhihu.py --all
```

### 翻訳内容を確認してから投稿（ドライラン）

```bash
python scripts/post-to-zhihu.py --dry-run articles/my-article.md
```

### 投稿済み記事の一覧を確認

```bash
python scripts/post-to-zhihu.py --list
```

### 既投稿記事を強制再投稿

```bash
python scripts/post-to-zhihu.py --force articles/my-article.md
```

---

## 投稿履歴の管理

投稿済み記事は `scripts/zhihu-posted.json` で管理されます。

```json
{
  "2026-03-08-vibe-coding.md": {
    "url": "https://zhuanlan.zhihu.com/p/12345678",
    "zhihu_id": 12345678,
    "zh_title": "Vibe Coding完全指南：让AI用「氛围」帮你写代码的新方式",
    "original_title": "Vibe Coding完全ガイド：AIに「雰囲気」で頼んでコードを書いてもらう新スタイル",
    "posted_at": "2026-03-15T12:00:00Z"
  }
}
```

このファイルはGitHubActionsから自動でコミットされ、履歴管理されます。

---

## 注意事項

### 知乎の利用規約について

知乎の非公式APIを使用しているため、以下の点に注意してください：

- APIの仕様は予告なく変更される可能性があります
- 大量の自動投稿は知乎の利用規約に違反する可能性があります
- Cookieは定期的に期限が切れるため、更新が必要です
- 知乎のToSに従い、スパム的な投稿は避けてください

### 翻訳品質について

Claude APIによる翻訳は高品質ですが、技術用語の翻訳が適切でない場合があります。重要な記事は投稿前に翻訳内容を確認することをお勧めします。`--dry-run` オプションが便利です。

---

## まとめ

## まとめ（構想段階）

設計として想定している仕組み：

- **新記事投稿時**：`main` へpushするだけで自動的に知乎にも投稿される
- **既存記事**：コマンド一つで手動投稿できる
- **重複投稿防止**：JSONで投稿履歴を管理
- **翻訳品質**：Claude API (claude-opus-4-6) による高品質な翻訳

ただし前述の通り、これは**現時点では未検証の構想**です。Cookie管理の煩雑さや非公式API固有のリスクを考えると、実用化にはまだハードルがあります。

まずは公式APIが整っているQiita・はてなブログ・note.comの同期を安定稼働させることを優先しています。知乎については状況を見ながら検討を続けます。

---

## 参考リンク

- [Anthropic Claude API ドキュメント](https://docs.anthropic.com/)
- [知乎 (Zhihu) 公式サイト](https://www.zhihu.com)
- [GitHub Actions ドキュメント](https://docs.github.com/ja/actions)
