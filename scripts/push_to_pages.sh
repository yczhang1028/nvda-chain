#!/bin/bash
# Push updated dashboard to GitHub Pages
set -e

TOKEN_FILE="$HOME/.github/.env"
if [ ! -f "$TOKEN_FILE" ]; then
  echo "ERROR: token file not found"
  exit 1
fi

GITHUB_TOKEN=$(head -1 "$TOKEN_FILE" | tr -d '\n\r ')

cd /home/ubuntu/hermes_share/nvda_chain

git add index.html data/prices.json data/upstream_feeds.json data/news/ data/stocks.json analysis/ 2>/dev/null
git commit -m "daily update $(date +%Y-%m-%d)" || true
git push "https://yczhang1028:${GITHUB_TOKEN}@github.com/yczhang1028/nvda-chain.git" main
echo "✓ pushed to GitHub Pages"
