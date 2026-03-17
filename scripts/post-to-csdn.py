#!/usr/bin/env python3
"""
Zenn記事を中国語に翻訳してCSDN（中国最大の技術ブログサイト）に投稿するスクリプト
Seleniumによるブラウザ自動化を使用（ローカル実行専用）

使い方:
  # 初回セットアップ（ブラウザを開いてCSDNにログインし、Cookieを保存）
  python scripts/post-to-csdn.py --setup

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

  # ブラウザを表示して実行（デバッグ用）
  python scripts/post-to-csdn.py --no-headless articles/my-article.md

必要な環境変数:
  DEEPL_API_KEY  - DeepL API キー（翻訳用）
                   https://www.deepl.com/en/pro#developer で無料登録可能（月50万文字無料）

初回のみ必要な操作:
  --setup オプションでブラウザを開き、手動でCSDNにログインしてEnterを押す。
  Cookieが scripts/csdn-cookies.json に保存され、次回以降は自動ログインされる。
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

import deepl
import frontmatter
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

SCRIPTS_DIR = Path(__file__).parent
REPO_ROOT = SCRIPTS_DIR.parent
POSTED_TRACKING_FILE = SCRIPTS_DIR / "csdn-posted.json"
COOKIES_FILE = SCRIPTS_DIR / "csdn-cookies.json"
ARTICLES_DIR = REPO_ROOT / "articles"
ZENN_USER = "long910"
PLATFORM_NAME = "csdn"
SYNC_PLATFORMS_FILE = REPO_ROOT / ".github" / "sync-platforms.json"

CSDN_LOGIN_URL = "https://passport.csdn.net/login"
CSDN_EDITOR_URL = "https://editor.csdn.net/md/"
CSDN_HOME_URL = "https://www.csdn.net"


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
    content = re.sub(
        r":::message\n.*?Claude Code.*?:::\n?",
        "",
        content,
        flags=re.DOTALL
    )
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
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


def translate_to_chinese(title: str, content: str) -> tuple[str, str]:
    """DeepL APIを使用して日本語記事を簡体字中国語に翻訳する"""
    api_key = os.environ.get("DEEPL_API_KEY")
    if not api_key:
        raise ValueError("DEEPL_API_KEY 環境変数が設定されていません")

    translator = deepl.Translator(api_key)

    # コードブロックをプレースホルダーで保護
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

    # コードブロックを復元
    for i, block in enumerate(code_blocks):
        zh_content = zh_content.replace(f"CODEBLOCK{i}ENDCODE", block)

    return zh_title, zh_content


def build_driver(headless: bool = True) -> webdriver.Chrome:
    """Chromeドライバーを構築する"""
    options = ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


class CSDNSeleniumClient:
    """SeleniumによるCSDNブラウザ自動化クライアント"""

    def __init__(self, headless: bool = True):
        self.driver = build_driver(headless=headless)
        self.wait = WebDriverWait(self.driver, 30)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.driver.quit()

    def load_cookies(self) -> bool:
        """保存済みCookieを読み込む。成功すればTrue"""
        if not COOKIES_FILE.exists():
            return False
        # Cookieをセットするにはまず対象ドメインに移動が必要
        self.driver.get(CSDN_HOME_URL)
        with open(COOKIES_FILE) as f:
            cookies = json.load(f)
        for cookie in cookies:
            # selenium が受け付けない余分なキーを除去
            cookie.pop("sameSite", None)
            try:
                self.driver.add_cookie(cookie)
            except Exception:
                pass
        self.driver.refresh()
        time.sleep(2)
        return True

    def save_cookies(self) -> None:
        """現在のCookieをファイルに保存する"""
        cookies = self.driver.get_cookies()
        with open(COOKIES_FILE, "w") as f:
            json.dump(cookies, f, indent=2)
        print(f"  Cookieを保存しました: {COOKIES_FILE}")

    def is_logged_in(self) -> bool:
        """ログイン状態を確認する"""
        self.driver.get(CSDN_HOME_URL)
        time.sleep(2)
        # ログイン済みならアバター要素やユーザー名が表示される
        indicators = [
            ".avatar",
            ".user-info",
            "#csdn-toolbar-profile-image",
            ".toolbar-profile",
        ]
        for selector in indicators:
            try:
                self.driver.find_element(By.CSS_SELECTOR, selector)
                return True
            except Exception:
                pass
        # URLにloginが含まれていなければログイン済みとみなす
        return "login" not in self.driver.current_url

    def setup_login(self) -> None:
        """手動ログインを促してCookieを保存するセットアップフロー"""
        print("ブラウザを開きます。CSDNにログインしてください。")
        print(f"ログインページ: {CSDN_LOGIN_URL}")
        self.driver.get(CSDN_LOGIN_URL)
        input("\nCSDNへのログインが完了したらEnterを押してください...")
        if self.is_logged_in():
            self.save_cookies()
            print("セットアップ完了。次回から自動ログインされます。")
        else:
            print("警告: ログイン状態を確認できませんでした。Cookieは保存しませんでした。")

    def post_article(
        self,
        title: str,
        markdown_content: str,
        tags: list[str],
    ) -> str:
        """記事をCSDNに投稿してURLを返す"""
        print("  エディタを開いています...")
        self.driver.get(CSDN_EDITOR_URL)

        # タイトル入力欄が現れるまで待機
        try:
            title_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#titleInput"))
            )
        except TimeoutException:
            # セレクタが変わっている場合のフォールバック
            title_input = self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "input[placeholder*='标题'], input[placeholder*='题目']")
                )
            )

        # タイトルをセット
        title_input.click()
        title_input.send_keys(Keys.CONTROL + "a")
        title_input.send_keys(title)
        time.sleep(0.5)

        # Markdownエディタにコンテンツをセット（CodeMirror / 独自エディタ対応）
        print("  コンテンツを入力しています...")
        self._set_editor_content(markdown_content)
        time.sleep(1)

        # 「发布文章」ボタンをクリック
        print("  公開ダイアログを開いています...")
        publish_btn = self._find_publish_button()
        publish_btn.click()
        time.sleep(2)

        # タグを入力
        if tags:
            self._set_tags(tags)

        # 最終公開ボタンをクリック
        print("  記事を公開しています...")
        confirm_btn = self._find_confirm_publish_button()
        confirm_btn.click()
        time.sleep(3)

        # 公開後のURLを取得
        url = self._get_published_url()
        return url

    def _set_editor_content(self, content: str) -> None:
        """エディタにMarkdownコンテンツをセットする"""
        # 方法1: CodeMirror JavaScript API
        try:
            self.driver.execute_script("""
                var cm = document.querySelector('.CodeMirror');
                if (cm && cm.CodeMirror) {
                    cm.CodeMirror.setValue(arguments[0]);
                    return true;
                }
                return false;
            """, content)
            time.sleep(0.5)
            # 正しくセットされたか確認
            val = self.driver.execute_script("""
                var cm = document.querySelector('.CodeMirror');
                if (cm && cm.CodeMirror) return cm.CodeMirror.getValue();
                return '';
            """)
            if val and len(val) > 10:
                return
        except Exception:
            pass

        # 方法2: contenteditable / textarea に直接セット
        try:
            editor = self.driver.find_element(
                By.CSS_SELECTOR,
                ".editor-section textarea, .markdown-editor textarea"
            )
            self.driver.execute_script(
                "arguments[0].value = arguments[1];", editor, content
            )
            editor.send_keys(" ")  # 変更イベントをトリガー
            editor.send_keys(Keys.BACK_SPACE)
            return
        except Exception:
            pass

        # 方法3: クリップボード経由（最終手段）
        self.driver.execute_script(
            f"navigator.clipboard.writeText({json.dumps(content)});"
        )
        editor_area = self.driver.find_element(
            By.CSS_SELECTOR, ".editor-section, .CodeMirror, [contenteditable='true']"
        )
        editor_area.click()
        editor_area.send_keys(Keys.CONTROL + "a")
        editor_area.send_keys(Keys.CONTROL + "v")

    def _find_publish_button(self):
        """「発布文章」ボタンを探す"""
        selectors = [
            "button.btn-publish",
            "button.publish-btn",
            "//button[contains(text(),'发布文章')]",
            "//button[contains(text(),'发布')]",
        ]
        for sel in selectors:
            try:
                if sel.startswith("//"):
                    return self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, sel))
                    )
                else:
                    return self.wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                    )
            except TimeoutException:
                continue
        raise RuntimeError("発布文章ボタンが見つかりませんでした")

    def _set_tags(self, tags: list[str]) -> None:
        """公開ダイアログでタグを入力する"""
        try:
            tag_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".tags-box input, .tag-input input, input[placeholder*='标签']")
                )
            )
            for tag in tags[:5]:
                tag_input.send_keys(tag)
                time.sleep(0.3)
                tag_input.send_keys(Keys.ENTER)
                time.sleep(0.3)
        except TimeoutException:
            print("  警告: タグ入力欄が見つかりませんでした（スキップ）")

    def _find_confirm_publish_button(self):
        """公開確認ボタンを探す"""
        selectors = [
            "//button[contains(text(),'确定发布')]",
            "//button[contains(text(),'发布')]",
            ".dialog-footer .btn-primary",
            ".sure.btn",
        ]
        for sel in selectors:
            try:
                if sel.startswith("//"):
                    return WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, sel))
                    )
                else:
                    return WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                    )
            except TimeoutException:
                continue
        raise RuntimeError("公開確認ボタンが見つかりませんでした")

    def _get_published_url(self) -> str:
        """公開後の記事URLを取得する"""
        # 公開後にエディタURLに記事IDが含まれる場合
        current = self.driver.current_url
        # URLが blog.csdn.net/... に変わっていれば成功
        if "blog.csdn.net" in current and "/article/details/" in current:
            return current

        # エディタURLからIDを抽出 (?id=XXXXXXX)
        match = re.search(r"[?&]id=(\d+)", current)
        if match:
            return f"https://blog.csdn.net/article/details/{match.group(1)}"

        # 成功ダイアログからリンクを探す
        try:
            link = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "a[href*='blog.csdn.net']")
                )
            )
            return link.get_attribute("href")
        except TimeoutException:
            pass

        # フォールバック: 現在のURLを返す
        return current


def setup_cookies(headless: bool = False) -> None:
    """初回セットアップ: 手動ログインしてCookieを保存する"""
    with CSDNSeleniumClient(headless=headless) as client:
        client.setup_login()


def post_article(
    filepath: str,
    dry_run: bool = False,
    force: bool = False,
    headless: bool = True,
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

    metadata, content = parse_article(path)
    title = metadata.get("title", path.stem)

    if not metadata.get("published", True):
        print(f"  スキップ（下書き）: {filename}")
        return None

    content = clean_zenn_content(content)

    print(f"  翻訳中: {title}")
    zh_title, zh_content = translate_to_chinese(title, content)
    print(f"  翻訳完了: {zh_title}")

    topics = metadata.get("topics", [])
    zh_tags = topics[:5] if topics else []

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

    if not COOKIES_FILE.exists():
        print("エラー: Cookieファイルが見つかりません。先に --setup を実行してください。")
        return None

    with CSDNSeleniumClient(headless=headless) as client:
        print("  Cookieでログイン中...")
        client.load_cookies()

        if not client.is_logged_in():
            print("エラー: ログインに失敗しました。--setup を再実行してください。")
            return None

        print("  ログイン確認済み")
        url = client.post_article(zh_title, zh_content, zh_tags)

    print(f"  公開完了: {url}")

    posted_articles[filename] = {
        "url": url,
        "zh_title": zh_title,
        "original_title": title,
        "posted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    save_posted_articles(posted_articles)

    return url


def main():
    parser = argparse.ArgumentParser(
        description="Zenn記事を中国語に翻訳してCSDNに投稿する（Selenium版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "articles",
        nargs="*",
        help="投稿する記事ファイルのパス",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="初回セットアップ: ブラウザを開いてログインしCookieを保存する",
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
        "--no-headless",
        action="store_true",
        help="ブラウザを画面に表示して実行する（デバッグ用）",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="投稿済み記事の一覧を表示する",
    )

    args = parser.parse_args()
    headless = not args.no_headless

    if args.setup:
        setup_cookies(headless=False)  # セットアップは必ず画面表示
        return

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

    if args.all:
        target_articles = sorted(ARTICLES_DIR.glob("*.md"))
    elif args.articles:
        target_articles = [Path(a) for a in args.articles]
    else:
        parser.print_help()
        sys.exit(1)

    success_count = 0
    skip_count = 0
    error_count = 0

    for article in target_articles:
        try:
            url = post_article(
                str(article),
                dry_run=args.dry_run,
                force=args.force,
                headless=headless,
            )
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
