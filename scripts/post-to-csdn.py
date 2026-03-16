#!/usr/bin/env python3
"""
Zenn記事を中国語に翻訳してCSDN（中国最大の技術ブログサイト）に投稿するスクリプト

使い方:
  # 特定の記事を投稿
  python scripts/post-to-csdn.py articles/2026-03-15-my-article.md

  # 複数記事を指定
  python scripts/post-to-csdn.py articles/article1.md articles/article2.md

  # 未投稿の全記事を投稿
  python scripts/post-to-csdn.py --all

  # 翻訳のみ確認（実際には投稿しない）
  python scripts/post-to-csdn.py --dry-run articles/my-article.md

  # 既投稿でも強制再投稿
  python scripts/post-to-csdn.py --force articles/my-article.md

必要な環境変数:
  ANTHROPIC_API_KEY  - Claude API キー（翻訳用）
  CSDN_COOKIE        - CSDNのログイン済みCookie文字列
                       (UserToken を含む必要がある)
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
import requests

CSDN_API_BASE = "https://blog-console-api.csdn.net"
SCRIPTS_DIR = Path(__file__).parent
REPO_ROOT = SCRIPTS_DIR.parent
POSTED_TRACKING_FILE = SCRIPTS_DIR / "csdn-posted.json"
ARTICLES_DIR = REPO_ROOT / "articles"
ZENN_USER = "long910"
PLATFORM_NAME = "csdn"
SYNC_PLATFORMS_FILE = REPO_ROOT / ".github" / "sync-platforms.json"


def is_excluded(filename: str) -> bool:
    """sync-platforms.json の exclude_articles に含まれるか確認する"""
    if not SYNC_PLATFORMS_FILE.exists():
        return False
    with open(SYNC_PLATFORMS_FILE) as f:
        config = json.load(f)
    exclude_list = (
        config.get("platforms", {})
        .get(PLATFORM_NAME, {})
        .get("exclude_articles", [])
    )
    return filename in exclude_list


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
    content = re.sub(r"@\[youtube\]\([^)]+\)", "[YouTube动画]", content)

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
        translated_title = lines[0].replace("TITLE:", "").strip()

    translated_content = "\n".join(translated_content_lines).strip()

    if not translated_content:
        parts = response.split("---\n", 1)
        if len(parts) > 1:
            translated_content = parts[1].strip()
        else:
            translated_content = response

    return translated_title, translated_content


class CSDNClient:
    """CSDN APIクライアント"""

    def __init__(self, cookie: str):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://editor.csdn.net/",
            "Origin": "https://editor.csdn.net",
            "Content-Type": "application/json;charset=UTF-8",
            "X-Ca-Key": "203803574",
        })

        # Cookie文字列をパース
        for item in cookie.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                self.session.cookies.set(key.strip(), value.strip())

        # UserTokenをAuthorizationヘッダーにも設定
        user_token = self.session.cookies.get("UserToken", "")
        if user_token:
            self.session.headers["Authorization"] = user_token
        else:
            print("警告: UserToken cookieが見つかりません。投稿に失敗する可能性があります。")

    def verify_auth(self) -> bool:
        """認証状態を確認する"""
        resp = self.session.get(
            "https://passport.csdn.net/v1/register/pc/getUserInfo/byParam"
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 200:
                user_data = data.get("data", {})
                print(f"ログイン確認: {user_data.get('userName', '不明')}")
                return True
        print(f"認証エラー: {resp.status_code} - {resp.text[:200]}")
        return False

    def save_article(
        self,
        title: str,
        markdown_content: str,
        tags: list[str],
        article_id: Optional[str] = None,
    ) -> str:
        """記事を保存（作成または更新）して記事IDを返す"""
        # 説明文を生成（最初の200文字）
        description = re.sub(r"[#*`\[\]()>]", "", markdown_content)
        description = re.sub(r"\s+", " ", description).strip()[:200]

        payload = {
            "title": title,
            "markdowncontent": markdown_content,
            "content": markdown_content,  # CSDNはmarkdownそのまま受け付ける
            "description": description,
            "tags": ",".join(tags[:5]),  # 最大5タグ
            "categories": "",
            "type": "original",  # original=オリジナル, reprint=転載, translated=翻訳
            "status": 0,  # 0=下書き, 1=公開
            "is_markdown": 1,
            "authorized_status": False,
            "check_original": False,
            "source": "pc",
        }

        if article_id:
            payload["id"] = article_id

        resp = self.session.post(
            f"{CSDN_API_BASE}/v1/postedit/save",
            json=payload,
        )

        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"記事保存失敗: HTTP {resp.status_code}\n{resp.text}"
            )

        data = resp.json()
        if data.get("code") != 200:
            raise RuntimeError(
                f"記事保存失敗: {data.get('msg', '不明なエラー')}\n{resp.text}"
            )

        return str(data["data"]["id"])

    def publish_article(self, article_id: str) -> str:
        """記事を公開してURLを返す"""
        resp = self.session.post(
            f"{CSDN_API_BASE}/v1/postedit/save",
            json={
                "id": article_id,
                "status": 1,  # 公開
            },
        )

        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"公開失敗: HTTP {resp.status_code}\n{resp.text}"
            )

        data = resp.json()
        if data.get("code") != 200:
            raise RuntimeError(
                f"公開失敗: {data.get('msg', '不明なエラー')}\n{resp.text}"
            )

        return f"https://blog.csdn.net/article/details/{article_id}"


def post_article(
    filepath: str,
    dry_run: bool = False,
    force: bool = False,
) -> Optional[str]:
    """Zenn記事をCSDNに投稿する"""
    path = Path(filepath)
    if not path.exists():
        print(f"エラー: ファイルが見つかりません: {filepath}")
        return None

    filename = path.name

    if is_excluded(filename):
        print(f"  スキップ（sync-platforms.json で除外）: {filename}")
        return None

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

    # タグを取得
    topics = metadata.get("topics", [])
    zh_tags = topics[:5] if topics else []

    # 出典フッターを追加
    zenn_url = f"https://zenn.dev/{ZENN_USER}/articles/{path.stem}"
    zh_content += (
        f"\n\n---\n\n"
        f"> 本文由日文翻译而来，原文发布于 [Zenn]({zenn_url})\n"
        f"> 作者: [{ZENN_USER}](https://zenn.dev/{ZENN_USER})"
    )

    if dry_run:
        print(f"  [DRY RUN] タイトル: {zh_title}")
        print(f"  [DRY RUN] タグ: {zh_tags}")
        print(f"  [DRY RUN] コンテンツ長: {len(zh_content)} 文字")
        print(f"  [DRY RUN] コンテンツプレビュー（先頭500文字）:\n{zh_content[:500]}")
        return None

    # CSDNに投稿
    cookie = os.environ.get("CSDN_COOKIE")
    if not cookie:
        print("エラー: CSDN_COOKIE 環境変数が設定されていません")
        return None

    client = CSDNClient(cookie)

    print("  認証確認中...")
    if not client.verify_auth():
        print("エラー: CSDNへの認証に失敗しました。Cookieを確認してください。")
        return None

    # 既存記事IDがあれば更新、なければ新規作成
    existing_id = None
    if filename in posted_articles and force:
        existing_id = posted_articles[filename].get("csdn_id")

    print("  記事保存中（下書き）...")
    article_id = client.save_article(zh_title, zh_content, zh_tags, existing_id)

    print(f"  記事公開中 (ID: {article_id})...")
    url = client.publish_article(article_id)

    print(f"  公開完了: {url}")

    # 投稿履歴を更新
    posted_articles[filename] = {
        "url": url,
        "csdn_id": article_id,
        "zh_title": zh_title,
        "original_title": title,
        "posted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    save_posted_articles(posted_articles)

    return url


def main():
    parser = argparse.ArgumentParser(
        description="Zenn記事を中国語に翻訳してCSDNに投稿する",
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
