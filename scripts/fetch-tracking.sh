#!/usr/bin/env bash
# tracking-data ブランチから追跡JSONをローカルに取得する
# ローカルでスクリプトを実行する前に呼び出すこと
# 使い方: ./scripts/fetch-tracking.sh

set -e

TRACKING_FILES=(
  "scripts/qiita-posted.json"
  "scripts/hatena-posted.json"
  "scripts/note-posted.json"
  "scripts/wechat-posted.json"
  "scripts/zhihu-posted.json"
  "scripts/csdn-posted.json"
)

if ! git ls-remote --exit-code origin tracking-data > /dev/null 2>&1; then
  echo "tracking-data ブランチがまだ存在しません。スキップします。"
  exit 0
fi

git fetch origin tracking-data

for file in "${TRACKING_FILES[@]}"; do
  if git show origin/tracking-data:"$file" > "$file" 2>/dev/null; then
    echo "取得: $file"
  fi
done

echo "完了: 追跡ファイルを tracking-data ブランチから取得しました"
