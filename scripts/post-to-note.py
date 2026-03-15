#!/usr/bin/env python3
"""
Zenn記事をnote.comに投稿するスクリプト（非公式API使用）

⚠️  注意: note.comは公式APIを公開していません。
    このスクリプトはリバースエンジニアリングされた内部APIを使用しており、
    仕様変更により予告なく動作しなくなる可能性があります。

使い方:
  python scripts/post-to-note.py articles/2026-03-15-my-article.md
  python scripts/post-to-note.py --all
  python scripts/post-to-note.py --dry-run articles/my-article.md
  python scripts/post-to-note.py --force articles/my-article.md
  python scripts/post-to-note.py --draft articles/my-article.md
  python scripts/post-to-note.py --list

必要な環境変数:
  NOTE_EMAIL     - note.comのログインメールアドレス
  NOTE_PASSWORD  - note.comのログインパスワード
  NOTE_USER_ID   - note.comのユーザーID（URLに使われるID、例: long910）
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

SCRIPTS_DIR = Path(__file__).parent
REPO_ROOT = SCRIPTS_DIR.parent
POSTED_TRACKING_FILE = SCRIPTS_DIR / "note-posted.json"
ARTICLES_DIR = REPO_ROOT / "articles"
ZENN_USER = "long910"
PLATFORM_NAME = "note"
SYNC_PLATFORMS_FILE = REPO_ROOT / ".github" / "sync-platforms.json"

NOTE_API_BASE = "https://note.com/api/v1"
NOTE_API_V2 = "https://note.com/api/v2"


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
    post = frontmatter.load(str(filepath))
    return dict(post.metadata), post.content


def convert_zenn_to_note(content: str) -> str:
    """Zenn固有の記法をnote.com互換のMarkdownに変換する"""

    # Claude Codeメッセージブロックを削除
    content = re.sub(
        r":::message\n.*?Claude Code.*?:::\n?",
        "",
        content,
        flags=re.DOTALL,
    )

    # :::message alert → 太字警告
    content = re.sub(
        r":::message alert\n(.*?):::",
        lambda m: "**⚠️ 注意:** " + m.group(1).strip().replace("\n", "\n> "),
        content,
        flags=re.DOTALL,
    )

    # :::message → 太字メモ
    content = re.sub(
        r":::message\n(.*?):::",
        lambda m: "**💡 メモ:** " + m.group(1).strip().replace("\n", "\n> "),
        content,
        flags=re.DOTALL,
    )

    # :::details → 折りたたみなし（note.comはHTMLを制限するため展開表示）
    content = re.sub(
        r":::details\s+(.*?)\n(.*?):::",
        lambda m: f"**{m.group(1).strip()}**\n\n{m.group(2).strip()}",
        content,
        flags=re.DOTALL,
    )

    # 残りの ::: タグを除去
    content = re.sub(r":::\w*\s*\n?", "", content)

    # YouTube埋め込みをURLリンクに変換
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
    return content + f"\n\n---\n\nこの記事は[Zenn]({zenn_url})でも公開しています。"


class NoteComClient:
    """note.com 非公式APIクライアント

    ⚠️ note.comは公式APIを提供していないため、内部APIを使用しています。
    仕様は予告なく変更される可能性があります。
    """

    def __init__(self, email: str, password: str, user_id: str):
        self.user_id = user_id
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://note.com/",
            "Origin": "https://note.com",
            "Content-Type": "application/json",
        })
        self._login(email, password)

    def _login(self, email: str, password: str) -> None:
        """メールアドレスとパスワードでログインしセッションCookieを取得する"""
        resp = self.session.post(
            f"{NOTE_API_BASE}/sessions",
            json={"login": email, "password": password},
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"ログイン失敗: HTTP {resp.status_code}\n{resp.text[:200]}"
            )
        # レスポンスからCSRFトークンを取得して設定
        data = resp.json()
        token = data.get("data", {}).get("token") or data.get("token")
        if token:
            self.session.headers["X-Note-Token"] = token
        print(f"  ログイン成功: {self.user_id}")

    def verify_auth(self) -> bool:
        """認証状態を確認する"""
        resp = self.session.get(
            f"{NOTE_API_V2}/creators/{self.user_id}"
        )
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            name = data.get("nickname") or data.get("urlname", self.user_id)
            print(f"  ユーザー確認: {name}")
            return True
        print(f"  認証エラー: HTTP {resp.status_code}")
        return False

    def create_draft(
        self,
        title: str,
        body: str,
        hashtags: list[str],
    ) -> str:
        """下書き記事を作成してIDを返す"""
        payload = {
            "name": title,
            "body": body,
            "hashtag_notes_attributes": [{"name": tag} for tag in hashtags],
            "status": "draft",
        }
        resp = self.session.post(
            f"{NOTE_API_BASE}/text_notes",
            json=payload,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"下書き作成失敗: HTTP {resp.status_code}\n{resp.text[:500]}"
            )
        data = resp.json()
        note_data = data.get("data", data)
        note_id = note_data.get("id") or note_data.get("key")
        if not note_id:
            raise RuntimeError(f"IDが取得できませんでした: {data}")
        return str(note_id)

    def publish(self, note_id: str) -> str:
        """下書きを公開してURLを返す"""
        resp = self.session.patch(
            f"{NOTE_API_BASE}/text_notes/{note_id}",
            json={"status": "published"},
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"公開失敗: HTTP {resp.status_code}\n{resp.text[:500]}"
            )
        return f"https://note.com/{self.user_id}/n/{note_id}"

    def create_and_publish(
        self,
        title: str,
        body: str,
        hashtags: list[str],
    ) -> tuple[str, str]:
        """下書き作成と公開を一度に行う（原子的投稿）"""
        payload = {
            "name": title,
            "body": body,
            "hashtag_notes_attributes": [{"name": tag} for tag in hashtags],
            "status": "published",
        }
        resp = self.session.post(
            f"{NOTE_API_BASE}/text_notes",
            json=payload,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"投稿失敗: HTTP {resp.status_code}\n{resp.text[:500]}"
            )
        data = resp.json()
        note_data = data.get("data", data)
        note_id = str(note_data.get("id") or note_data.get("key", ""))
        url = f"https://note.com/{self.user_id}/n/{note_id}"
        return note_id, url


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

    content = convert_zenn_to_note(content)
    content = add_zenn_crosslink(content, path.stem)

    if dry_run:
        print(f"  [DRY RUN] タイトル: {title}")
        print(f"  [DRY RUN] タグ: {topics}")
        print(f"  [DRY RUN] コンテンツ（先頭300文字）:\n{content[:300]}")
        return None

    email = os.environ.get("NOTE_EMAIL")
    password = os.environ.get("NOTE_PASSWORD")
    user_id = os.environ.get("NOTE_USER_ID")
    if not all([email, password, user_id]):
        print("エラー: NOTE_EMAIL / NOTE_PASSWORD / NOTE_USER_ID を設定してください")
        return None

    client = NoteComClient(email, password, user_id)

    if not client.verify_auth():
        return None

    if draft:
        print("  下書き作成中...")
        note_id = client.create_draft(title, content, topics)
        url = f"https://note.com/{user_id}/n/{note_id}"
        print(f"  下書き保存完了: {url}")
    else:
        print("  投稿中...")
        note_id, url = client.create_and_publish(title, content, topics)
        print(f"  投稿完了: {url}")

    posted_articles[filename] = {
        "url": url,
        "note_id": note_id,
        "title": title,
        "posted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    save_posted_articles(posted_articles)
    return url


def main():
    parser = argparse.ArgumentParser(
        description="Zenn記事をnote.comに投稿する（非公式API使用）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("articles", nargs="*", help="投稿する記事ファイルのパス")
    parser.add_argument("--all", action="store_true", help="未投稿の公開済み記事をすべて投稿")
    parser.add_argument("--dry-run", action="store_true", help="変換のみ実行し投稿しない")
    parser.add_argument("--force", action="store_true", help="投稿済みでも強制再投稿")
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
                time.sleep(2)  # レート制限対策
        except Exception as e:
            print(f"エラー ({article.name}): {e}", file=sys.stderr)
            error_count += 1
            if not args.all:
                raise

    print(f"\n完了: 成功={success_count}, スキップ={skip_count}, エラー={error_count}")


if __name__ == "__main__":
    main()
