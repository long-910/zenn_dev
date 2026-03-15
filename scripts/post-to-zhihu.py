#!/usr/bin/env python3
"""
Zenn記事を中国語に翻訳して知乎（Zhihu）に投稿するスクリプト

使い方:
  # 特定の記事を投稿
  python scripts/post-to-zhihu.py articles/2026-03-15-my-article.md

  # 複数記事を指定
  python scripts/post-to-zhihu.py articles/article1.md articles/article2.md

  # 未投稿の全記事を投稿
  python scripts/post-to-zhihu.py --all

  # 翻訳のみ確認（実際には投稿しない）
  python scripts/post-to-zhihu.py --dry-run articles/my-article.md

  # 既投稿でも強制再投稿
  python scripts/post-to-zhihu.py --force articles/my-article.md

必要な環境変数:
  ANTHROPIC_API_KEY  - Claude API キー（翻訳用）
  ZHIHU_COOKIE       - 知乎のログイン済みCookie文字列
                       (z_c0 と _xsrf を含む必要がある)
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

import anthropic
import frontmatter
import markdown
import requests

ZHIHU_API_BASE = "https://zhuanlan.zhihu.com"
SCRIPTS_DIR = Path(__file__).parent
REPO_ROOT = SCRIPTS_DIR.parent
POSTED_TRACKING_FILE = SCRIPTS_DIR / "zhihu-posted.json"
ARTICLES_DIR = REPO_ROOT / "articles"
ZENN_USER = "long910"


def load_posted_articles() -> dict:
    if POSTED_TRACKING_FILE.exists():
        with open(POSTED_TRACKING_FILE) as f:
            return json.load(f)
    return {}


def save_posted_articles(data: dict) -> None:
    with open(POSTED_TRACKING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def parse_article(filepath: Path) -> tuple[dict, str]:
    """Zenn記事のフロントマターと本文を解析する"""
    post = frontmatter.load(str(filepath))
    return dict(post.metadata), post.content


def clean_zenn_content(content: str) -> str:
    """Zenn固有の記法をMarkdownに変換する"""
    # Claude Codeメッセージブロックを削除
    content = re.sub(
        r":::message\n.*?Claude Code.*?:::\n?",
        "",
        content,
        flags=re.DOTALL
    )

    # :::message (alert) ブロックをBlockquoteに変換
    content = re.sub(
        r":::message alert\n(.*?):::",
        r"> ⚠️ **注意:** \1",
        content,
        flags=re.DOTALL
    )
    content = re.sub(
        r":::message\n(.*?):::",
        r"> 💡 **提示:** \1",
        content,
        flags=re.DOTALL
    )

    # :::details ブロックをセクションに変換
    content = re.sub(
        r":::details\s+(.*?)\n(.*?):::",
        r"**\1**\n\n\2",
        content,
        flags=re.DOTALL
    )

    # 残りの ::: タグを削除
    content = re.sub(r":::\w*\s*", "", content)
    content = re.sub(r":::", "", content)

    # Zenn YouTube埋め込みを削除
    content = re.sub(r"@\[youtube\]\([^)]+\)", "[YouTube動画]", content)

    # Zenn SlideShare埋め込みを削除
    content = re.sub(r"@\[slideshare\]\([^)]+\)", "[SlideShare]", content)

    # 連続する空行を最大2行に圧縮
    content = re.sub(r"\n{3,}", "\n\n", content)

    return content.strip()


def translate_to_chinese(title: str, content: str) -> tuple[str, str]:
    """Claude APIを使用して日本語記事を中国語に翻訳する"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY 環境変数が設定されていません")

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""请将以下日文技术文章翻译成简体中文。

翻译要求：
1. 保持所有代码块不变（代码块内的内容不要翻译）
2. 保持所有URL链接不变
3. 保持Markdown格式不变（标题、列表、粗体等）
4. 技术术语使用中文技术社区常用的翻译或保留原文
5. 翻译要自然流畅，符合中文技术文章的表达习惯
6. 人名、产品名、工具名保留原文或使用通用中文名称

请用如下格式回复：
TITLE: [翻译后的标题]
---
[翻译后的正文内容]

原文标题: {title}

原文内容:
{content}"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}]
    )

    response = message.content[0].text

    # レスポンスをパース
    lines = response.split("\n")
    translated_title = ""
    translated_content_lines = []
    in_content = False

    for line in lines:
        if line.startswith("TITLE: "):
            translated_title = line[7:].strip()
        elif line == "---" and translated_title and not in_content:
            in_content = True
        elif in_content:
            translated_content_lines.append(line)

    if not translated_title:
        # フォールバック: 最初の行をタイトルとして使用
        translated_title = lines[0].replace("TITLE:", "").strip()

    translated_content = "\n".join(translated_content_lines).strip()

    if not translated_content:
        # フォールバック: ---以降の内容全体を使用
        parts = response.split("---\n", 1)
        if len(parts) > 1:
            translated_content = parts[1].strip()
        else:
            translated_content = response

    return translated_title, translated_content


def markdown_to_html(md_content: str) -> str:
    """Zhihu投稿用にMarkdownをHTMLに変換する"""
    md = markdown.Markdown(
        extensions=[
            "fenced_code",
            "tables",
            "nl2br",
        ]
    )
    return md.convert(md_content)


class ZhihuClient:
    """知乎APIクライアント（非公式APIを使用）"""

    def __init__(self, cookie: str):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.zhihu.com/",
            "Origin": "https://www.zhihu.com",
            "Content-Type": "application/json",
        })

        # Cookie文字列をパース
        for item in cookie.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                self.session.cookies.set(key.strip(), value.strip())

        # XSRFトークンをヘッダーに設定
        xsrf = self.session.cookies.get("_xsrf", "")
        if xsrf:
            self.session.headers["x-xsrftoken"] = xsrf
        else:
            print("警告: _xsrf cookieが見つかりません。投稿に失敗する可能性があります。")

    def verify_auth(self) -> bool:
        """認証状態を確認する"""
        resp = self.session.get("https://www.zhihu.com/api/v4/me")
        if resp.status_code == 200:
            data = resp.json()
            print(f"ログイン確認: {data.get('name', '不明')}")
            return True
        print(f"認証エラー: {resp.status_code}")
        return False

    def create_draft(self) -> int:
        """記事の下書きを作成する"""
        resp = self.session.post(
            f"{ZHIHU_API_BASE}/api/articles/drafts",
            json={"delta_time": 0}
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"下書き作成失敗: HTTP {resp.status_code}\n{resp.text}"
            )
        return resp.json()["id"]

    def update_draft(self, article_id: int, title: str, html_content: str) -> None:
        """下書きのタイトルと内容を更新する"""
        resp = self.session.patch(
            f"{ZHIHU_API_BASE}/api/articles/{article_id}",
            json={
                "title": title,
                "content": html_content,
                "delta_time": 0,
            }
        )
        if resp.status_code not in (200, 201, 204):
            raise RuntimeError(
                f"下書き更新失敗: HTTP {resp.status_code}\n{resp.text}"
            )

    def publish(self, article_id: int) -> str:
        """記事を公開してURLを返す"""
        resp = self.session.post(
            f"{ZHIHU_API_BASE}/api/articles/{article_id}/publish",
            json={
                "disclaimer_type": "none",
                "disclaimer_status": "none",
            }
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"公開失敗: HTTP {resp.status_code}\n{resp.text}"
            )
        return f"https://zhuanlan.zhihu.com/p/{article_id}"


def post_article(
    filepath: str,
    dry_run: bool = False,
    force: bool = False,
) -> Optional[str]:
    """Zenn記事を知乎に投稿する"""
    path = Path(filepath)
    if not path.exists():
        print(f"エラー: ファイルが見つかりません: {filepath}")
        return None

    filename = path.name
    posted_articles = load_posted_articles()

    if filename in posted_articles and not force:
        url = posted_articles[filename]["url"]
        print(f"投稿済み: {filename} -> {url}")
        return url

    print(f"\n処理中: {filename}")

    # 記事をパース
    metadata, content = parse_article(path)
    title = metadata.get("title", path.stem)

    # 非公開記事はスキップ
    if not metadata.get("published", True):
        print(f"  スキップ（下書き）: {filename}")
        return None

    # Zenn固有記法をクリーン
    content = clean_zenn_content(content)

    # 翻訳
    print(f"  翻訳中: {title}")
    zh_title, zh_content = translate_to_chinese(title, content)
    print(f"  翻訳完了: {zh_title}")

    # 出典フッターを追加
    zenn_url = f"https://zenn.dev/{ZENN_USER}/articles/{path.stem}"
    zh_content += (
        f"\n\n---\n\n"
        f"> 本文由日文翻译而来，原文发布于 [Zenn]({zenn_url})\n"
        f"> 作者: [{ZENN_USER}](https://zenn.dev/{ZENN_USER})"
    )

    # MarkdownをHTMLに変換
    html_content = markdown_to_html(zh_content)

    if dry_run:
        print(f"  [DRY RUN] タイトル: {zh_title}")
        print(f"  [DRY RUN] コンテンツ長: {len(html_content)} 文字")
        print(f"  [DRY RUN] HTMLプレビュー（先頭500文字）:\n{html_content[:500]}")
        return None

    # 知乎に投稿
    cookie = os.environ.get("ZHIHU_COOKIE")
    if not cookie:
        print("エラー: ZHIHU_COOKIE 環境変数が設定されていません")
        return None

    client = ZhihuClient(cookie)

    print("  認証確認中...")
    if not client.verify_auth():
        print("エラー: 知乎への認証に失敗しました。Cookieを確認してください。")
        return None

    print("  下書き作成中...")
    article_id = client.create_draft()

    print(f"  下書き更新中 (ID: {article_id})...")
    client.update_draft(article_id, zh_title, html_content)

    print("  公開中...")
    url = client.publish(article_id)

    print(f"  公開完了: {url}")

    # 投稿履歴を更新
    posted_articles[filename] = {
        "url": url,
        "zhihu_id": article_id,
        "zh_title": zh_title,
        "original_title": title,
        "posted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    save_posted_articles(posted_articles)

    return url


def main():
    parser = argparse.ArgumentParser(
        description="Zenn記事を中国語に翻訳して知乎（Zhihu）に投稿する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "articles",
        nargs="*",
        help="投稿する記事ファイルのパス",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="未投稿の公開済み記事をすべて投稿する",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="翻訳のみ実行し、実際には投稿しない",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="投稿済みでも強制的に再投稿する",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="投稿済み記事の一覧を表示する",
    )

    args = parser.parse_args()

    # 投稿済みリストの表示
    if args.list:
        posted = load_posted_articles()
        if not posted:
            print("投稿済み記事はありません")
            return
        print(f"投稿済み記事 ({len(posted)}件):")
        for filename, info in sorted(posted.items()):
            print(f"  {filename}")
            print(f"    タイトル: {info.get('zh_title', 'N/A')}")
            print(f"    URL: {info.get('url', 'N/A')}")
            print(f"    投稿日: {info.get('posted_at', 'N/A')}")
        return

    # 投稿対象の決定
    if args.all:
        target_articles = sorted(ARTICLES_DIR.glob("*.md"))
    elif args.articles:
        target_articles = [Path(a) for a in args.articles]
    else:
        parser.print_help()
        sys.exit(1)

    # 投稿実行
    success_count = 0
    skip_count = 0
    error_count = 0

    for article in target_articles:
        try:
            url = post_article(str(article), dry_run=args.dry_run, force=args.force)
            if url:
                success_count += 1
            else:
                skip_count += 1
        except Exception as e:
            print(f"エラー ({article.name}): {e}", file=sys.stderr)
            error_count += 1
            if not args.all:
                raise

    print(f"\n完了: 成功={success_count}, スキップ={skip_count}, エラー={error_count}")


if __name__ == "__main__":
    main()
