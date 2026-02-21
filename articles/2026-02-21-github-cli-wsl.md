---
title: "WSLでGitHub CLIを使いこなす：インストールから実践的な活用まで"
emoji: "🐙"
type: "tech"
topics: ["githubcli", "wsl", "ubuntu", "git", "github"]
published: true
published_at: "2026-02-21 10:00"
---

# WSLでGitHub CLIを使いこなす：インストールから実践的な活用まで

## はじめに

GitHub CLI（`gh`）は、GitHubの操作をターミナルから直接行えるコマンドラインツールです。PRの作成・レビュー、Issue管理、リリース作成など、ブラウザを開かずにGitHubのほぼすべての操作が可能になります。本記事では、WSL（Ubuntu）へのインストールから実践的な使い方まで、備忘録としてまとめます。

## GitHub CLIとは

GitHub CLIを使うと、以下のような操作をターミナルから実行できます。

- Pull Requestの作成・マージ・レビュー
- Issueの作成・クローズ・コメント
- リポジトリのクローン・作成・フォーク
- GitHub Actionsの実行確認
- リリースの作成・管理
- Gistの操作

## インストール

### aptリポジトリを使用したインストール（推奨）

Ubuntu/DebianにはGitHubの公式aptリポジトリを追加してインストールします。

```bash
# 必要なパッケージのインストール
sudo apt update
sudo apt install -y curl gpg

# GitHubのGPGキーを追加
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | \
  sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg

# aptリポジトリの追加
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | \
  sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null

# インストール
sudo apt update
sudo apt install -y gh
```

### インストール確認

```bash
gh --version
# gh version 2.x.x (2024-xx-xx)
```

### アップデート方法

```bash
sudo apt update && sudo apt upgrade gh
```

## 認証設定

### WSLでのブラウザ認証の問題と対策

WSLでそのまま`gh auth login`を実行すると、以下のエラーが出てブラウザが起動しないことがあります。

```
gzip: stdin: not in gzip format
```

これはWSLがデフォルトでWindowsブラウザを開く手段を持っていないために発生します。以下のどちらかの方法で対処してください。

#### 方法A：wsluをインストールしてブラウザ連携を修正（推奨）

```bash
# wsluをインストール（wslviewが含まれる）
sudo apt install -y wslu

# xdg-openをwslviewに向ける
sudo ln -sf /usr/bin/wslview /usr/local/bin/xdg-open
```

これでWindowsのデフォルトブラウザが自動で開くようになります。

#### 方法B：Personal Access Token（PAT）で認証

ブラウザ連携なしでも確実に認証できます。

**Step 1：GitHubでPATを作成**

`https://github.com/settings/tokens/new` にアクセスして以下のScopeを選択します。

- `repo`（全チェック）
- `workflow`
- `read:org`
- `gist`

「Generate token」でトークン（`ghp_`で始まる文字列）を作成・コピーします。

**Step 2：`gh auth login`でトークンを貼り付け**

```bash
gh auth login
```

```
? How would you like to authenticate GitHub CLI?
  Login with a web browser
> Paste an authentication token    ← これを選ぶ
```

コピーしたトークンを貼り付けてEnterで認証完了です。

### 対話的な認証（ブラウザ経由）

```bash
gh auth login
```

以下の選択肢が表示されます。

```
? What account do you want to log into?
> GitHub.com
  GitHub Enterprise Server

? What is your preferred protocol for Git operations on this host?
> HTTPS
  SSH

? Authenticate Git with your GitHub credentials?
> Yes
  No

? How would you like to authenticate GitHub CLI?
> Login with a web browser
  Paste an authentication token
```

「Login with a web browser」を選択すると、ワンタイムコードが表示されます。ブラウザでそのコードを入力すれば認証完了です。

### SSHキーを使った認証

```bash
gh auth login --git-protocol ssh
```

SSHキーがない場合は自動で生成してGitHubに登録するか、既存のキーを選択できます。

### 認証状態の確認

```bash
gh auth status
```

```
github.com
  ✓ Logged in to github.com account long910 (keyring)
  - Active account: true
  - Git operations protocol: https
  - Token: gho_****
  - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
```

### 認証のリフレッシュ（スコープ追加）

```bash
# 追加のスコープを要求する場合
gh auth refresh -s delete_repo
```

### ログアウト

```bash
gh auth logout
```

## 基本設定

### デフォルトエディタの設定

```bash
gh config set editor vim
# または
gh config set editor nano
# VSCodeを使う場合
gh config set editor "code --wait"
```

### デフォルトプロトコルの設定

```bash
# HTTPSを使用
gh config set git_protocol https

# SSHを使用
gh config set git_protocol ssh
```

### 設定の確認

```bash
gh config list
```

## リポジトリ操作

### リポジトリのクローン

```bash
# リポジトリをクローン
gh repo clone owner/repo-name

# 自分のリポジトリをクローン（オーナー省略可）
gh repo clone repo-name
```

### リポジトリの作成

```bash
# カレントディレクトリをGitHubリポジトリとして作成
gh repo create

# 対話的に設定が進みます
# ? Repository name (フォルダ名がデフォルト)
# ? Description
# ? Visibility  [Use arrows to move, type to filter]
# > Public
#   Private
#   Internal

# オプションを指定して作成
gh repo create my-new-repo --public --description "My awesome project" --clone
```

### リポジトリのフォーク

```bash
gh repo fork owner/repo-name

# クローンも同時に行う
gh repo fork owner/repo-name --clone
```

### リポジトリ情報の表示

```bash
# リポジトリの情報をブラウザで開く
gh repo view --web

# ターミナルで表示
gh repo view

# 別のリポジトリを表示
gh repo view owner/repo-name
```

### リポジトリ一覧

```bash
# 自分のリポジトリ一覧
gh repo list

# 特定のユーザーのリポジトリ一覧
gh repo list username

# フィルタリング
gh repo list --public --limit 20
```

## Pull Request操作

### PRの作成

```bash
# 対話的に作成（推奨）
gh pr create

# オプションを指定して作成
gh pr create \
  --title "feat: ○○機能を追加" \
  --body "## 変更内容\n- ○○を実装\n\n## テスト方法\n- ○○を確認" \
  --base main \
  --draft

# テンプレートファイルを使用
gh pr create --template ".github/PULL_REQUEST_TEMPLATE.md"
```

### PRの一覧表示

```bash
# オープン中のPR一覧
gh pr list

# すべてのPRを表示
gh pr list --state all

# 自分のPRのみ表示
gh pr list --author @me

# レビュー待ちのPR
gh pr list --search "review-requested:@me"
```

### PRの詳細確認

```bash
# カレントブランチのPRを表示
gh pr view

# PR番号を指定
gh pr view 123

# ブラウザで開く
gh pr view 123 --web
```

### PRのチェックアウト

```bash
# PR番号を指定してチェックアウト
gh pr checkout 123
```

### PRのレビュー

```bash
# レビューを承認
gh pr review 123 --approve

# 変更をリクエスト
gh pr review 123 --request-changes --body "○○の修正をお願いします"

# コメントのみ
gh pr review 123 --comment --body "LGTMです！"
```

### PRのマージ

```bash
# マージ（デフォルト：マージコミット）
gh pr merge 123

# スカッシュマージ
gh pr merge 123 --squash

# リベースマージ
gh pr merge 123 --rebase

# マージ後にブランチを削除
gh pr merge 123 --squash --delete-branch
```

### PRのクローズと再オープン

```bash
gh pr close 123
gh pr reopen 123
```

## Issue操作

### Issueの作成

```bash
# 対話的に作成
gh issue create

# オプションを指定
gh issue create \
  --title "バグ：○○が正常に動作しない" \
  --body "## 再現手順\n1. ○○を実行\n2. ○○が発生\n\n## 期待する動作\n○○が正常に動作すること" \
  --label "bug" \
  --assignee @me
```

### Issueの一覧表示

```bash
# オープン中のIssue一覧
gh issue list

# クローズ済みも含める
gh issue list --state all

# ラベルで絞り込み
gh issue list --label "bug"

# 担当者で絞り込み
gh issue list --assignee @me
```

### Issueの詳細確認

```bash
gh issue view 456

# ブラウザで開く
gh issue view 456 --web
```

### Issueのコメント

```bash
gh issue comment 456 --body "確認しました。対応します。"
```

### Issueのクローズ

```bash
# クローズ
gh issue close 456

# クローズ時にコメントを追加
gh issue close 456 --comment "修正しました。PR #123 でマージ済みです。"
```

## GitHub Actionsの操作

### ワークフローの一覧表示

```bash
gh workflow list
```

### ワークフローの手動実行

```bash
# ワークフロー名またはIDで実行
gh workflow run "CI"

# ブランチを指定
gh workflow run "CI" --ref feature/my-branch

# 入力値を指定（workflow_dispatchのinputsがある場合）
gh workflow run "Deploy" --field environment=production
```

### ワークフロー実行履歴の確認

```bash
gh run list

# 特定のワークフローの履歴
gh run list --workflow="CI"
```

### ワークフロー実行のログ確認

```bash
# 最新の実行を確認
gh run view

# 実行IDを指定
gh run view 1234567890

# ログをストリーミング表示（実行中）
gh run watch 1234567890

# ログをダウンロード
gh run view 1234567890 --log
```

## リリース操作

### リリースの作成

```bash
# タグを指定してリリース作成
gh release create v1.0.0

# オプションを指定
gh release create v1.0.0 \
  --title "v1.0.0 - 初期リリース" \
  --notes "## 変更内容\n- ○○機能を追加" \
  --prerelease

# ファイルをアタッチ
gh release create v1.0.0 ./dist/app.tar.gz ./dist/app.zip
```

### リリースの一覧表示

```bash
gh release list
```

### リリースの詳細確認

```bash
gh release view v1.0.0
```

## 実践的な活用例

### 1. 毎日のワークフロー自動化

```bash
# 今日のPRレビューリストを確認
gh pr list --search "review-requested:@me" --json number,title,author --jq '.[] | "#\(.number) \(.title) by \(.author.login)"'
```

### 2. Issue駆動開発

```bash
# Issueを作成してそのままブランチを切る
ISSUE_NUMBER=$(gh issue create --title "新機能：○○" --body "詳細" | grep -oP '(?<=issues/)\d+')
git checkout -b "feature/issue-${ISSUE_NUMBER}-description"
```

### 3. PRを作成してDraftにする

```bash
# 作業中のPRをDraftとして作成
gh pr create --draft --title "WIP: ○○機能" --body "作業中"

# 準備ができたらDraftを解除
gh pr ready
```

### 4. PRのレビューURLをSlackに共有

```bash
# PRのURLを取得してクリップボードにコピー（WSL環境）
gh pr view --json url --jq '.url' | clip.exe
```

### 5. 複数リポジトリの管理

```bash
# エイリアスを設定
gh alias set prs 'pr list --author @me --state open'

# 使用
gh prs
```

### 6. GitHub CLI エイリアスの活用

```bash
# よく使うコマンドをエイリアス登録
gh alias set co 'pr checkout'
gh alias set rv 'pr review'

# 一覧表示
gh alias list
```

## 便利なTips

### JSON出力とjqの組み合わせ

多くのコマンドが`--json`オプションをサポートしており、`jq`と組み合わせると強力です。

```bash
# PRのタイトルとURLを一覧表示
gh pr list --json number,title,url | jq '.[] | "\(.number): \(.title) - \(.url)"'

# Issueのラベル別集計
gh issue list --json labels --jq '[.[].labels[].name] | group_by(.) | map({label: .[0], count: length})'
```

### 環境変数の設定

```bash
# デフォルトリポジトリの設定（カレントディレクトリが別リポジトリでも操作可能）
export GH_REPO=owner/repo-name

# GitHubトークンの環境変数設定（CI環境などで使用）
export GH_TOKEN=ghp_xxxxxxxxxxxx
```

### APIの直接呼び出し

`gh api`コマンドでGitHub APIを直接呼び出せます。

```bash
# 自分のユーザー情報を取得
gh api user

# リポジトリのスター数を取得
gh api repos/owner/repo-name --jq '.stargazers_count'

# GraphQL APIの使用
gh api graphql -f query='
{
  viewer {
    login
    repositories(first: 5, orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes {
        name
        updatedAt
      }
    }
  }
}'
```

## コマンド早見表

| 操作 | コマンド |
|------|---------|
| 認証 | `gh auth login` |
| 認証状態確認 | `gh auth status` |
| リポジトリクローン | `gh repo clone owner/repo` |
| リポジトリ作成 | `gh repo create` |
| PR作成 | `gh pr create` |
| PR一覧 | `gh pr list` |
| PRをチェックアウト | `gh pr checkout 123` |
| PRをマージ | `gh pr merge 123` |
| Issue作成 | `gh issue create` |
| Issue一覧 | `gh issue list` |
| Issueをクローズ | `gh issue close 123` |
| ワークフロー実行 | `gh workflow run "CI"` |
| 実行ログ確認 | `gh run view` |
| リリース作成 | `gh release create v1.0.0` |
| APIを叩く | `gh api /user` |

## まとめ

GitHub CLIを活用することで、GitHubとのやり取りをターミナルに集約でき、開発効率が大幅に向上します。特にWSL環境では、Linuxのコマンドラインツールと組み合わせることでさらに強力な自動化が可能です。

まずは`gh auth login`で認証し、普段よく使う操作（PRの作成・確認など）から徐々に使い始めると習得しやすいです。

## 参考リンク

- [GitHub CLI 公式ドキュメント](https://cli.github.com/manual/)
- [GitHub CLI リリースページ](https://github.com/cli/cli/releases)
- [GitHub CLI リポジトリ](https://github.com/cli/cli)
