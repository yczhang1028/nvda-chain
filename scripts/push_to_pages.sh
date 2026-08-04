#!/bin/bash
# Push updated dashboard to GitHub Pages
set -e

TOKEN_FILE="$HOME/.github/.env"
if [ ! -f "$TOKEN_FILE" ]; then
  echo "ERROR: token file not found"
  exit 1
fi

GIT_TOKEN=$(grep GITHUB_TOKEN "$TOKEN_FILE" | cut -d= -f2 | tr -d '\n\r ')

cd /home/ubuntu/hermes_share/nvda_chain

git remote set-url origin "https://${GIT_TOKEN}@github.com/yczhang1028/nvda-chain.git"
git add nvda_chain/index.html nvda_chain/analysis.html data/prices.json data/upstream_feeds.json data/news/ data/stocks.json analysis/ 2>/dev/null
git commit -m "daily update $(date +%Y-%m-%d)" || true
git push origin main
echo "✓ pushed to GitHub Pages"
