#!/usr/bin/env python3
"""
Zenn記事を中国語に翻訳して微信公众号（WeChat Official Account）に投稿するスクリプト

使い方:
  python scripts/post-to-wechat.py articles/2026-03-15-my-article.md
  python scripts/post-to-wechat.py --all
  python scripts/post-to-wechat.py --dry-run articles/my-article.md
  python scripts/post-to-wechat.py --force articles/my-article.md  # 既存記事を上書き
  python scripts/post-to-wechat.py --publish articles/my-article.md  # 下書きを公開まで実行
  python scripts/post-to-wechat.py --list

必要な環境変数:
  DEEPL_API_KEY          - DeepL API キー（翻訳用）
  WECHAT_APP_ID          - 微信公众号のAppID
  WECHAT_APP_SECRET      - 微信公众号のAppSecret
  WECHAT_THUMB_MEDIA_ID  - 記事カバー画像のmedia_id（永久素材）
                           事前に微信公众号管理画面またはAPIでアップロードし取得すること

注意:
  WeChat公众号APIは記事を「草稿箱（下書き）」に作成します。
  実際の配信（群发）は管理画面から手動で行うか、--publish オプションを使用してください。
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import deepl
import frontmatter
import markdown as md_lib

WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"
SCRIPTS_DIR = Path(__file__).parent
REPO_ROOT = SCRIPTS_DIR.parent
POSTED_TRACKING_FILE = SCRIPTS_DIR / "wechat-posted.json"
ARTICLES_DIR = REPO_ROOT / "articles"
ZENN_USER = "long910"
PLATFORM_NAME = "wechat"
SYNC_PLATFORMS_FILE = REPO_ROOT / ".github" / "sync-platforms.json"


def is_excluded(filename: str) -> bool:
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


def clean_zenn_content(content: str) -> str:
    """Zenn固有の記法をMarkdownに変換する"""
    content = re.sub(
        r":::message\n.*?Claude Code.*?:::\n?",
        "",
        content,
        flags=re.DOTALL
    )
    content = re.sub(
        r":::message alert\n(.*?):::",
        r"> ⚠️ \1",
        content,
        flags=re.DOTALL
    )
    content = re.sub(
        r":::message\n(.*?):::",
        r"> 💡 \1",
        content,
        flags=re.DOTALL
    )
    content = re.sub(
        r":::details\s+(.*?)\n(.*?):::",
        r"**\1**\n\n\2",
        content,
        flags=re.DOTALL
    )
    content = re.sub(r":::\w*\s*", "", content)
    content = re.sub(r":::", "", content)
    content = re.sub(r"@\[youtube\]\([^)]+\)", "[YouTube动画]", content)
    content = re.sub(r"@\[slideshare\]\([^)]+\)", "[SlideShare]", content)
    # 外部画像はWeChat CDN未対応のためリンクテキストに変換
    content = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"[图片: \1]", content)
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


def translate_to_chinese(title: str, content: str) -> tuple[str, str]:
    """DeepL APIを使用して日本語記事を簡体字中国語に翻訳する"""
    api_key = os.environ.get("DEEPL_API_KEY")
    if not api_key:
        raise ValueError("DEEPL_API_KEY 環境変数が設定されていません")

    translator = deepl.Translator(api_key)

    code_blocks: list[str] = []

    def replace_code_block(m: re.Match) -> str:
        code_blocks.append(m.group(0))
        return f"CODEBLOCK{len(code_blocks) - 1}ENDCODE"

    protected = re.sub(r"```[\s\S]*?```", replace_code_block, content)

    results = translator.translate_text(
        [title, protected], source_lang="JA", target_lang="ZH"
    )
    zh_title = results[0].text
    zh_content = results[1].text

    for i, block in enumerate(code_blocks):
        zh_content = zh_content.replace(f"CODEBLOCK{i}ENDCODE", block)

    return zh_title, zh_content


def markdown_to_wechat_html(content: str) -> str:
    """MarkdownをWeChat公众号向けHTMLに変換する"""
    html = md_lib.markdown(
        content,
        extensions=["fenced_code", "tables", "nl2br", "sane_lists"],
    )
    # コードブロックにWeChat互換スタイルを適用
    html = re.sub(
        r"<pre><code[^>]*>",
        '<pre style="background:#f4f4f4;padding:12px;border-radius:4px;overflow-x:auto;font-size:14px;"><code>',
        html,
    )
    # blockquoteにスタイルを適用
    html = re.sub(
        r"<blockquote>",
        '<blockquote style="border-left:4px solid #ccc;margin:0;padding:0 16px;color:#666;">',
        html,
    )
    return html


def add_crosslink_footer(content: str, zenn_slug: str) -> str:
    zenn_url = f"https://zenn.dev/{ZENN_USER}/articles/{zenn_slug}"
    return content + (
        f"\n\n---\n\n"
        f"> 本文由日文翻译而来，原文发布于 [Zenn]({zenn_url})\n"
        f"> 作者: [{ZENN_USER}](https://zenn.dev/{ZENN_USER})"
    )


class WeChatClient:
    """微信公众号 API クライアント"""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    def _get_access_token(self) -> str:
        """access_tokenを取得する（キャッシュ付き）"""
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        url = (
            f"{WECHAT_API_BASE}/token"
            f"?grant_type=client_credential"
            f"&appid={self.app_id}"
            f"&secret={self.app_secret}"
        )
        req = Request(url)
        with urlopen(req) as resp:
            data = json.loads(resp.read().decode())

        if "errcode" in data:
            raise RuntimeError(
                f"access_token取得失敗: {data.get('errmsg', '')} (code={data['errcode']})"
            )

        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + data["expires_in"] - 60
        return self._access_token

    def _api_post(self, path: str, payload: dict) -> dict:
        token = self._get_access_token()
        url = f"{WECHAT_API_BASE}/{path}?access_token={token}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urlopen(req) as resp:
                data = json.loads(resp.read().decode())
        except HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"API呼び出し失敗: HTTP {e.code}\n{error_body}") from e

        if data.get("errcode") and data["errcode"] != 0:
            raise RuntimeError(
                f"API エラー: {data.get('errmsg', '')} (code={data['errcode']})"
            )
        return data

    def verify_auth(self) -> bool:
        """認証確認"""
        try:
            token = self._get_access_token()
            print(f"  access_token取得成功: {token[:16]}...")
            return True
        except Exception as e:
            print(f"  認証エラー: {e}")
            return False

    def add_draft(
        self,
        title: str,
        html_content: str,
        digest: str,
        thumb_media_id: str,
        content_source_url: str = "",
    ) -> str:
        """草稿箱（下書き）に記事を追加してmedia_idを返す"""
        payload = {
            "articles": [
                {
                    "title": title,
                    "author": ZENN_USER,
                    "digest": digest,
                    "content": html_content,
                    "content_source_url": content_source_url,
                    "thumb_media_id": thumb_media_id,
                    "need_open_comment": 0,
                    "only_fans_can_comment": 0,
                }
            ]
        }
        data = self._api_post("draft/add", payload)
        return data["media_id"]

    def update_draft(
        self,
        media_id: str,
        title: str,
        html_content: str,
        digest: str,
        thumb_media_id: str,
        content_source_url: str = "",
    ) -> None:
        """既存の草稿を更新する"""
        payload = {
            "media_id": media_id,
            "index": 0,
            "articles": {
                "title": title,
                "author": ZENN_USER,
                "digest": digest,
                "content": html_content,
                "content_source_url": content_source_url,
                "thumb_media_id": thumb_media_id,
                "need_open_comment": 0,
                "only_fans_can_comment": 0,
            },
        }
        self._api_post("draft/update", payload)

    def publish_draft(self, media_id: str) -> str:
        """草稿を公開申請してpublish_idを返す"""
        data = self._api_post("freepublish/submit", {"media_id": media_id})
        return data.get("publish_id", "")


def post_article(
    filepath: str,
    dry_run: bool = False,
    force: bool = False,
    publish: bool = False,
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
        url = posted_articles[filename].get("url", "（草稿箱に保存済み）")
        print(f"投稿済み: {filename} -> {url}")
        return url

    print(f"\n処理中: {filename}")

    metadata, content = parse_article(path)
    title = metadata.get("title", path.stem)

    if not metadata.get("published", True):
        print(f"  スキップ（下書き）: {filename}")
        return None

    content = clean_zenn_content(content)

    print(f"  翻訳中: {title}")
    zh_title, zh_content = translate_to_chinese(title, content)
    print(f"  翻訳完了: {zh_title}")

    zh_content = add_crosslink_footer(zh_content, path.stem)

    # 摘要（digest）を生成（最初の140文字）
    digest = re.sub(r"[#*`\[\]()>]", "", zh_content)
    digest = re.sub(r"\s+", " ", digest).strip()[:140]

    html_content = markdown_to_wechat_html(zh_content)

    zenn_url = f"https://zenn.dev/{ZENN_USER}/articles/{path.stem}"

    if dry_run:
        print(f"  [DRY RUN] タイトル: {zh_title}")
        print(f"  [DRY RUN] 摘要: {digest[:80]}...")
        print(f"  [DRY RUN] HTMLコンテンツ長: {len(html_content)} 文字")
        return None

    app_id = os.environ.get("WECHAT_APP_ID")
    app_secret = os.environ.get("WECHAT_APP_SECRET")
    thumb_media_id = os.environ.get("WECHAT_THUMB_MEDIA_ID")

    if not all([app_id, app_secret, thumb_media_id]):
        missing = [
            k for k, v in {
                "WECHAT_APP_ID": app_id,
                "WECHAT_APP_SECRET": app_secret,
                "WECHAT_THUMB_MEDIA_ID": thumb_media_id,
            }.items() if not v
        ]
        print(f"エラー: 環境変数が設定されていません: {', '.join(missing)}")
        return None

    client = WeChatClient(app_id, app_secret)

    print("  認証確認中...")
    if not client.verify_auth():
        return None

    if is_update and force:
        existing_media_id = posted_articles[filename].get("media_id")
        if existing_media_id:
            print("  草稿を更新中...")
            client.update_draft(
                existing_media_id, zh_title, html_content, digest,
                thumb_media_id, zenn_url
            )
            media_id = existing_media_id
        else:
            print("  media_idが不明のため新規作成します...")
            media_id = client.add_draft(
                zh_title, html_content, digest, thumb_media_id, zenn_url
            )
    else:
        print("  草稿箱に追加中...")
        media_id = client.add_draft(
            zh_title, html_content, digest, thumb_media_id, zenn_url
        )

    print(f"  草稿追加完了 (media_id: {media_id})")

    publish_id = ""
    if publish:
        print("  公開申請中...")
        publish_id = client.publish_draft(media_id)
        print(f"  公開申請完了 (publish_id: {publish_id})")

    posted_articles[filename] = {
        "media_id": media_id,
        "publish_id": publish_id,
        "url": f"（管理画面で確認: https://mp.weixin.qq.com/）",
        "zh_title": zh_title,
        "original_title": title,
        "posted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    save_posted_articles(posted_articles)

    return media_id


def main():
    parser = argparse.ArgumentParser(
        description="Zenn記事を中国語に翻訳して微信公众号に投稿する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("articles", nargs="*", help="投稿する記事ファイルのパス")
    parser.add_argument("--all", action="store_true", help="未投稿の公開済み記事をすべて投稿")
    parser.add_argument("--dry-run", action="store_true", help="翻訳のみ実行し投稿しない")
    parser.add_argument("--force", action="store_true", help="投稿済みでも強制上書き")
    parser.add_argument("--publish", action="store_true", help="草稿を公開申請まで実行する")
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
            print(f"    タイトル: {info.get('zh_title', 'N/A')}")
            print(f"    media_id: {info.get('media_id', 'N/A')}")
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
            result = post_article(
                str(article),
                dry_run=args.dry_run,
                force=args.force,
                publish=args.publish,
            )
            if result:
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
