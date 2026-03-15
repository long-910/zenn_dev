#!/usr/bin/env python3
"""
Zenn記事をQiitaに投稿するスクリプト（翻訳不要・日本語のまま投稿）

使い方:
  # 特定の記事を投稿
  python scripts/post-to-qiita.py articles/2026-03-15-my-article.md

  # 複数記事を指定
  python scripts/post-to-qiita.py articles/article1.md articles/article2.md

  # 未投稿の全記事を投稿
  python scripts/post-to-qiita.py --all

  # 翻訳のみ確認（実際には投稿しない）
  python scripts/post-to-qiita.py --dry-run articles/my-article.md

  # 既投稿でも強制再投稿（記事を更新）
  python scripts/post-to-qiita.py --force articles/my-article.md

  # 投稿済み記事の一覧表示
  python scripts/post-to-qiita.py --list

必要な環境変数:
  QIITA_TOKEN  - QiitaのアクセストークンAPI（write_qiita スコープが必要）
                 取得: https://qiita.com/settings/applications
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

import frontmatter
import requests

QIITA_API_BASE = "https://qiita.com/api/v2"
SCRIPTS_DIR = Path(__file__).parent
REPO_ROOT = SCRIPTS_DIR.parent
POSTED_TRACKING_FILE = SCRIPTS_DIR / "qiita-posted.json"
ARTICLES_DIR = REPO_ROOT / "articles"
ZENN_USER = "long910"
PLATFORM_NAME = "qiita"
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


def convert_zenn_to_qiita(content: str) -> str:
    """Zenn固有の記法をQiita互換のMarkdownに変換する"""

    # Claude Codeメッセージブロックを削除
    content = re.sub(
        r":::message\n.*?Claude Code.*?:::\n?",
        "",
        content,
        flags=re.DOTALL
    )

    # :::message alert → :::note alert
    content = re.sub(
        r":::message alert\n",
        ":::note alert\n",
        content
    )

    # :::message → :::note info
    content = re.sub(
        r":::message\n",
        ":::note info\n",
        content
    )

    # :::details title → <details><summary>title</summary> ... </details>
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

    # 残りの ::: タグを削除
    content = re.sub(r":::\w*\s*\n?", ":::\n", content)

    # YouTube埋め込みをリンクに変換
    content = re.sub(
        r"@\[youtube\]\(([^)]+)\)",
        r"https://www.youtube.com/watch?v=\1",
        content
    )

    # SlideShare埋め込みを削除
    content = re.sub(r"@\[slideshare\]\([^)]+\)", "[SlideShare]", content)

    # 連続する空行を最大2行に圧縮
    content = re.sub(r"\n{3,}", "\n\n", content)

    return content.strip()


def topics_to_qiita_tags(topics: list) -> list[dict]:
    """Zennのtopicsリストをqiitaのtags形式に変換する"""
    return [{"name": topic, "versions": []} for topic in (topics or [])]


def add_zenn_crosslink(content: str, zenn_slug: str) -> str:
    """ZennへのクロスリンクをQiita記事の末尾に追加する"""
    zenn_url = f"https://zenn.dev/{ZENN_USER}/articles/{zenn_slug}"
    crosslink = (
        f"\n\n---\n\n"
        f"> この記事は[Zenn]({zenn_url})でも公開しています。"
    )
    return content + crosslink


class QiitaClient:
    """Qiita API v2 クライアント"""

    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })

    def verify_auth(self) -> bool:
        """認証状態を確認する"""
        resp = self.session.get(f"{QIITA_API_BASE}/authenticated_user")
        if resp.status_code == 200:
            data = resp.json()
            print(f"ログイン確認: @{data.get('id', '不明')} ({data.get('name', '')})")
            return True
        print(f"認証エラー: HTTP {resp.status_code}")
        return False

    def create_item(
        self,
        title: str,
        body: str,
        tags: list[dict],
        private: bool = False,
    ) -> dict:
        """記事を新規作成する"""
        payload = {
            "title": title,
            "body": body,
            "tags": tags if tags else [{"name": "tech", "versions": []}],
            "private": private,
            "coediting": False,
            "tweet": False,
        }
        resp = self.session.post(
            f"{QIITA_API_BASE}/items",
            json=payload
        )
        if resp.status_code != 201:
            raise RuntimeError(
                f"記事作成失敗: HTTP {resp.status_code}\n{resp.text}"
            )
        return resp.json()

    def update_item(
        self,
        item_id: str,
        title: str,
        body: str,
        tags: list[dict],
    ) -> dict:
        """既存記事を更新する"""
        payload = {
            "title": title,
            "body": body,
            "tags": tags if tags else [{"name": "tech", "versions": []}],
        }
        resp = self.session.patch(
            f"{QIITA_API_BASE}/items/{item_id}",
            json=payload
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"記事更新失敗: HTTP {resp.status_code}\n{resp.text}"
            )
        return resp.json()

    def get_rate_limit(self) -> dict:
        """レート制限の残り回数を確認する"""
        resp = self.session.get(f"{QIITA_API_BASE}/rate_limit")
        return resp.json() if resp.status_code == 200 else {}


def post_article(
    filepath: str,
    dry_run: bool = False,
    force: bool = False,
    private: bool = False,
) -> Optional[str]:
    """Zenn記事をQiitaに投稿する"""
    path = Path(filepath)
    if not path.exists():
        print(f"エラー: ファイルが見つかりません: {filepath}")
        return None

    filename = path.name

    if is_excluded(filename):
        print(f"  スキップ（sync-platforms.json で除外）: {filename}")
        return None

    posted_articles = load_posted_articles()

    # 既投稿の場合は更新するか確認
    is_update = filename in posted_articles
    if is_update and not force:
        url = posted_articles[filename]["url"]
        print(f"投稿済み: {filename} -> {url}")
        return url

    print(f"\n処理中: {filename}")

    # 記事をパース
    metadata, content = parse_article(path)
    title = metadata.get("title", path.stem)
    topics = metadata.get("topics", [])

    # 非公開記事はスキップ（--private フラグがない場合）
    if not metadata.get("published", True) and not private:
        print(f"  スキップ（下書き）: {filename}")
        return None

    # Zenn記法をQiita互換に変換
    content = convert_zenn_to_qiita(content)

    # ZennへのクロスリンクをZenn記事のスラッグから生成
    zenn_slug = path.stem  # ファイル名（拡張子なし）がそのままZennのslug
    content = add_zenn_crosslink(content, zenn_slug)

    # Qiitaタグに変換
    tags = topics_to_qiita_tags(topics)

    if dry_run:
        print(f"  [DRY RUN] タイトル: {title}")
        print(f"  [DRY RUN] タグ: {[t['name'] for t in tags]}")
        print(f"  [DRY RUN] コンテンツ長: {len(content)} 文字")
        print(f"  [DRY RUN] コンテンツ（先頭300文字）:\n{content[:300]}")
        return None

    # Qiitaに投稿
    token = os.environ.get("QIITA_TOKEN")
    if not token:
        print("エラー: QIITA_TOKEN 環境変数が設定されていません")
        print("取得: https://qiita.com/settings/applications")
        return None

    client = QiitaClient(token)

    print("  認証確認中...")
    if not client.verify_auth():
        print("エラー: Qiitaへの認証に失敗しました。トークンを確認してください。")
        return None

    if is_update and force:
        item_id = posted_articles[filename]["item_id"]
        print(f"  記事更新中 (ID: {item_id})...")
        result = client.update_item(item_id, title, content, tags)
        url = result["url"]
        print(f"  更新完了: {url}")
    else:
        print("  記事作成中...")
        result = client.create_item(title, content, tags, private=private)
        url = result["url"]
        print(f"  投稿完了: {url}")

    # 投稿履歴を更新
    posted_articles[filename] = {
        "url": url,
        "item_id": result["id"],
        "title": title,
        "posted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    save_posted_articles(posted_articles)

    return url


def main():
    parser = argparse.ArgumentParser(
        description="Zenn記事をQiitaに投稿する",
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
        help="変換のみ実行し、実際には投稿しない",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="投稿済みでも強制的に更新する",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        help="限定公開で投稿する",
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
            print(f"    タイトル: {info.get('title', 'N/A')}")
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
            url = post_article(
                str(article),
                dry_run=args.dry_run,
                force=args.force,
                private=args.private,
            )
            if url:
                success_count += 1
            else:
                skip_count += 1
            # レート制限対策: 連続投稿時に少し待機
            if len(target_articles) > 1 and not args.dry_run:
                time.sleep(1)
        except Exception as e:
            print(f"エラー ({article.name}): {e}", file=sys.stderr)
            error_count += 1
            if not args.all:
                raise

    print(f"\n完了: 成功={success_count}, スキップ={skip_count}, エラー={error_count}")


if __name__ == "__main__":
    main()
