#!/usr/bin/env python3
"""
Zenn記事をはてなブログに投稿するスクリプト（AtomPub API使用）

使い方:
  python scripts/post-to-hatena.py articles/2026-03-15-my-article.md
  python scripts/post-to-hatena.py --all
  python scripts/post-to-hatena.py --dry-run articles/my-article.md
  python scripts/post-to-hatena.py --force articles/my-article.md  # 既存記事を更新
  python scripts/post-to-hatena.py --draft articles/my-article.md  # 下書きとして投稿
  python scripts/post-to-hatena.py --list

必要な環境変数:
  HATENA_ID       - はてなID (例: long910)
  HATENA_BLOG_ID  - ブログID (例: long910.hatenablog.com)
  HATENA_API_KEY  - APIキー (https://blog.hatena.ne.jp/my/config/detail から取得)
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import base64
import xml.etree.ElementTree as ET

import frontmatter

SCRIPTS_DIR = Path(__file__).parent
REPO_ROOT = SCRIPTS_DIR.parent
POSTED_TRACKING_FILE = SCRIPTS_DIR / "hatena-posted.json"
ARTICLES_DIR = REPO_ROOT / "articles"
ZENN_USER = "long910"
PLATFORM_NAME = "hatena"
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


# AtomPub XML名前空間
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "app": "http://www.w3.org/2007/app",
}


def load_posted_articles() -> dict:
    if POSTED_TRACKING_FILE.exists():
        with open(POSTED_TRACKING_FILE) as f:
            return json.load(f)
    return {}


def save_posted_articles(data: dict) -> None:
    with open(POSTED_TRACKING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def parse_article(filepath: Path) -> tuple[dict, str]:
    post = frontmatter.load(str(filepath))
    return dict(post.metadata), post.content


def convert_zenn_to_hatena(content: str) -> str:
    """Zenn固有の記法をはてなブログ互換のMarkdownに変換する"""

    # Claude Codeメッセージブロックを削除
    content = re.sub(
        r":::message\n.*?Claude Code.*?:::\n?",
        "",
        content,
        flags=re.DOTALL,
    )

    # :::message alert → > ⚠️ blockquote
    content = re.sub(
        r":::message alert\n(.*?):::",
        lambda m: "\n".join(
            f"> ⚠️ {line}" if i == 0 else f"> {line}"
            for i, line in enumerate(m.group(1).strip().splitlines())
        ),
        content,
        flags=re.DOTALL,
    )

    # :::message → > 💡 blockquote
    content = re.sub(
        r":::message\n(.*?):::",
        lambda m: "\n".join(
            f"> 💡 {line}" if i == 0 else f"> {line}"
            for i, line in enumerate(m.group(1).strip().splitlines())
        ),
        content,
        flags=re.DOTALL,
    )

    # :::details → <details><summary> HTML
    def replace_details(m):
        title = m.group(1).strip()
        body = m.group(2).strip()
        return f"<details>\n<summary>{title}</summary>\n\n{body}\n\n</details>"

    content = re.sub(
        r":::details\s+(.*?)\n(.*?):::",
        replace_details,
        content,
        flags=re.DOTALL,
    )

    # 残りの ::: タグを除去
    content = re.sub(r":::\w*\s*\n?", "", content)

    # YouTube埋め込みをリンクに変換
    content = re.sub(
        r"@\[youtube\]\(([^)]+)\)",
        r"https://www.youtube.com/watch?v=\1",
        content,
    )

    # SlideShare埋め込みを除去
    content = re.sub(r"@\[slideshare\]\([^)]+\)", "[SlideShare]", content)

    # 連続する空行を最大2行に圧縮
    content = re.sub(r"\n{3,}", "\n\n", content)

    return content.strip()


def add_zenn_crosslink(content: str, zenn_slug: str) -> str:
    zenn_url = f"https://zenn.dev/{ZENN_USER}/articles/{zenn_slug}"
    return content + f"\n\n---\n\n> この記事は[Zenn]({zenn_url})でも公開しています。"


def build_atom_entry(
    title: str,
    content: str,
    categories: list[str],
    draft: bool = False,
) -> bytes:
    """AtomPub形式のXMLエントリを生成する"""
    ET.register_namespace("", "http://www.w3.org/2005/Atom")
    ET.register_namespace("app", "http://www.w3.org/2007/app")

    entry = ET.Element("{http://www.w3.org/2005/Atom}entry")

    title_el = ET.SubElement(entry, "{http://www.w3.org/2005/Atom}title")
    title_el.text = title

    author = ET.SubElement(entry, "{http://www.w3.org/2005/Atom}author")
    name = ET.SubElement(author, "{http://www.w3.org/2005/Atom}name")
    name.text = os.environ.get("HATENA_ID", "")

    content_el = ET.SubElement(entry, "{http://www.w3.org/2005/Atom}content")
    content_el.set("type", "text/x-markdown")
    content_el.text = content

    for cat in categories:
        cat_el = ET.SubElement(entry, "{http://www.w3.org/2005/Atom}category")
        cat_el.set("term", cat)

    control = ET.SubElement(entry, "{http://www.w3.org/2007/app}control")
    draft_el = ET.SubElement(control, "{http://www.w3.org/2007/app}draft")
    draft_el.text = "yes" if draft else "no"

    xml_str = ET.tostring(entry, encoding="unicode", xml_declaration=False)
    return f'<?xml version="1.0" encoding="utf-8"?>\n{xml_str}'.encode("utf-8")


class HatenaClient:
    """はてなブログ AtomPub API クライアント"""

    def __init__(self, hatena_id: str, blog_id: str, api_key: str):
        self.hatena_id = hatena_id
        self.blog_id = blog_id
        self.api_key = api_key
        self.collection_url = (
            f"https://blog.hatena.ne.jp/{hatena_id}/{blog_id}/atom/entry"
        )
        credentials = f"{hatena_id}:{api_key}"
        self.auth_header = (
            "Basic " + base64.b64encode(credentials.encode()).decode()
        )

    def _request(self, method: str, url: str, data: bytes = None) -> str:
        headers = {
            "Authorization": self.auth_header,
            "Content-Type": "application/xml; charset=utf-8",
        }
        req = Request(url, data=data, headers=headers, method=method)
        with urlopen(req) as resp:
            return resp.read().decode("utf-8")

    def verify_auth(self) -> bool:
        """認証確認（サービス文書取得）"""
        service_url = (
            f"https://blog.hatena.ne.jp/{self.hatena_id}"
            f"/{self.blog_id}/atom"
        )
        try:
            self._request("GET", service_url)
            print(f"ログイン確認: {self.hatena_id} / {self.blog_id}")
            return True
        except HTTPError as e:
            print(f"認証エラー: HTTP {e.code}")
            return False

    def create_entry(
        self,
        title: str,
        content: str,
        categories: list[str],
        draft: bool = False,
    ) -> dict:
        """記事を新規投稿する"""
        body = build_atom_entry(title, content, categories, draft)
        try:
            resp_xml = self._request("POST", self.collection_url, body)
        except HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"投稿失敗: HTTP {e.code}\n{error_body}"
            ) from e
        return self._parse_entry(resp_xml)

    def update_entry(
        self,
        entry_url: str,
        title: str,
        content: str,
        categories: list[str],
        draft: bool = False,
    ) -> dict:
        """既存記事を更新する"""
        body = build_atom_entry(title, content, categories, draft)
        try:
            resp_xml = self._request("PUT", entry_url, body)
        except HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"更新失敗: HTTP {e.code}\n{error_body}"
            ) from e
        return self._parse_entry(resp_xml)

    @staticmethod
    def _parse_entry(xml_str: str) -> dict:
        """AtomエントリXMLから必要な情報を抽出する"""
        root = ET.fromstring(xml_str)
        result = {}

        # id (entry URL)
        id_el = root.find("{http://www.w3.org/2005/Atom}id")
        if id_el is not None:
            result["entry_url"] = id_el.text

        # alternate link (公開URL)
        for link in root.findall("{http://www.w3.org/2005/Atom}link"):
            if link.get("rel") == "alternate":
                result["url"] = link.get("href")
                break

        return result


def post_article(
    filepath: str,
    dry_run: bool = False,
    force: bool = False,
    draft: bool = False,
) -> Optional[str]:
    path = Path(filepath)
    if not path.exists():
        print(f"エラー: ファイルが見つかりません: {filepath}")
        return None

    filename = path.name

    if is_excluded(filename):
        print(f"  スキップ（sync-platforms.json で除外）: {filename}")
        return None

    posted_articles = load_posted_articles()

    is_update = filename in posted_articles
    if is_update and not force:
        url = posted_articles[filename]["url"]
        print(f"投稿済み: {filename} -> {url}")
        return url

    print(f"\n処理中: {filename}")

    metadata, content = parse_article(path)
    title = metadata.get("title", path.stem)
    topics = metadata.get("topics", [])

    if not metadata.get("published", True) and not draft:
        print(f"  スキップ（下書き）: {filename}")
        return None

    content = convert_zenn_to_hatena(content)
    content = add_zenn_crosslink(content, path.stem)

    if dry_run:
        print(f"  [DRY RUN] タイトル: {title}")
        print(f"  [DRY RUN] カテゴリ: {topics}")
        print(f"  [DRY RUN] コンテンツ（先頭300文字）:\n{content[:300]}")
        return None

    hatena_id = os.environ.get("HATENA_ID")
    blog_id = os.environ.get("HATENA_BLOG_ID")
    api_key = os.environ.get("HATENA_API_KEY")
    if not all([hatena_id, blog_id, api_key]):
        print("エラー: HATENA_ID / HATENA_BLOG_ID / HATENA_API_KEY を設定してください")
        return None

    client = HatenaClient(hatena_id, blog_id, api_key)

    print("  認証確認中...")
    if not client.verify_auth():
        return None

    if is_update and force:
        entry_url = posted_articles[filename]["entry_url"]
        print(f"  記事更新中...")
        result = client.update_entry(entry_url, title, content, topics, draft)
    else:
        print("  記事作成中...")
        result = client.create_entry(title, content, topics, draft)

    url = result.get("url", result.get("entry_url", ""))
    print(f"  {'下書き保存' if draft else '投稿'}完了: {url}")

    posted_articles[filename] = {
        "url": url,
        "entry_url": result.get("entry_url", ""),
        "title": title,
        "posted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    save_posted_articles(posted_articles)
    return url


def main():
    parser = argparse.ArgumentParser(
        description="Zenn記事をはてなブログに投稿する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("articles", nargs="*", help="投稿する記事ファイルのパス")
    parser.add_argument("--all", action="store_true", help="未投稿の公開済み記事をすべて投稿")
    parser.add_argument("--dry-run", action="store_true", help="変換のみ実行し投稿しない")
    parser.add_argument("--force", action="store_true", help="投稿済みでも強制更新")
    parser.add_argument("--draft", action="store_true", help="下書きとして保存")
    parser.add_argument("--list", action="store_true", help="投稿済み記事の一覧を表示")

    args = parser.parse_args()

    if args.list:
        posted = load_posted_articles()
        if not posted:
            print("投稿済み記事はありません")
            return
        print(f"投稿済み記事 ({len(posted)}件):")
        for filename, info in sorted(posted.items()):
            print(f"  {filename}")
            print(f"    URL: {info.get('url', 'N/A')}")
            print(f"    投稿日: {info.get('posted_at', 'N/A')}")
        return

    if args.all:
        target_articles = sorted(ARTICLES_DIR.glob("*.md"))
    elif args.articles:
        target_articles = [Path(a) for a in args.articles]
    else:
        parser.print_help()
        sys.exit(1)

    success_count = skip_count = error_count = 0
    for article in target_articles:
        try:
            url = post_article(
                str(article),
                dry_run=args.dry_run,
                force=args.force,
                draft=args.draft,
            )
            if url:
                success_count += 1
            else:
                skip_count += 1
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
