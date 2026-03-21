#!/usr/bin/env bash
# ローカルの追跡JSONを tracking-data ブランチに保存する
# ローカルでスクリプトを実行した後に呼び出すこと
# 使い方: ./scripts/push-tracking.sh

set -e

TRACKING_FILES=(
  "scripts/qiita-posted.json"
  "scripts/hatena-posted.json"
  "scripts/note-posted.json"
  "scripts/wechat-posted.json"
  "scripts/zhihu-posted.json"
  "scripts/csdn-posted.json"
)

# 存在するファイルだけ /tmp にコピー
EXISTING_FILES=()
for file in "${TRACKING_FILES[@]}"; do
  if [ -f "$file" ]; then
    tmpname="/tmp/tracking-$(basename "$file")"
    cp "$file" "$tmpname"
    EXISTING_FILES+=("$file")
  fi
done

if [ ${#EXISTING_FILES[@]} -eq 0 ]; then
  echo "追跡ファイルが見つかりません。スキップします。"
  exit 0
fi

git config user.name "$(git config --global user.name || echo 'local')"
git config user.email "$(git config --global user.email || echo 'local@local')"

if git ls-remote --exit-code origin tracking-data > /dev/null 2>&1; then
  git fetch origin tracking-data
  git checkout -b tracking-data-tmp origin/tracking-data 2>/dev/null || \
    git checkout tracking-data-tmp
else
  git checkout --orphan tracking-data-tmp
  git rm -rf . || true
fi

mkdir -p scripts
for file in "${EXISTING_FILES[@]}"; do
  tmpname="/tmp/tracking-$(basename "$file")"
  cp "$tmpname" "$file"
  git add "$file"
  echo "追加: $file"
done

if git diff --staged --quiet; then
  echo "追跡ファイルに変更なし"
else
  git commit -m "chore: Update tracking files (local)"
  for i in 1 2 3 4 5; do
    if git ls-remote --exit-code origin tracking-data > /dev/null 2>&1; then
      git pull --rebase origin tracking-data 2>/dev/null || true
    fi
    git push origin tracking-data-tmp:tracking-data && break
    echo "push失敗、リトライ $i/5"
    sleep $((i * 3))
  done
  echo "完了: tracking-data ブランチに保存しました"
fi

# main ブランチに戻る
git checkout main
