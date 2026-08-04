#!/usr/bin/env python3
"""Daily update: fetch prices + news, regen dashboard, push alert if big moves."""
import json, subprocess
from pathlib import Path

ROOT = Path.home() / "hermes_share" / "nvda_chain"

# 1) prices
subprocess.run(["python3", str(ROOT / "scripts" / "fetch_prices.py")], check=True)
# 2) individual stock news
subprocess.run(["python3", str(ROOT / "scripts" / "fetch_news.py")], check=True)
# 3) upstream theme feeds (NVIDIA + 国产推理卡)
subprocess.run(["python3", str(ROOT / "scripts" / "fetch_upstream.py")], check=True)
# 4) render
subprocess.run(["python3", str(ROOT / "scripts" / "render_dashboard.py")], check=True)

# 4) detect big moves (>5% 1-week)
prices = json.loads((ROOT / "data" / "prices.json").read_text())
alerts = []
for s in prices["stocks"]:
    r1w = s["returns"].get("1w")
    if r1w is None: continue
    if abs(r1w) >= 5:
        sign = "📈" if r1w > 0 else "📉"
        alerts.append(f"{sign} **{s['name']}** ({s['ticker']}) 1周 {r1w:+.1f}% · 现价 {s['last_price']:.2f}")

print(f"\n--- {len(alerts)} alerts ---")
for a in alerts:
    print(a)

# === 当日快照归档：把 prices.json / news/ / upstream_feeds.json 复制到 snapshots/YYYY-MM-DD/ ===
import shutil
from datetime import date
SNAP = ROOT / "data" / "snapshots" / date.today().isoformat()
SNAP.mkdir(parents=True, exist_ok=True)
for src in [ROOT/"data"/"prices.json", ROOT/"data"/"upstream_feeds.json"]:
    if src.exists():
        shutil.copy2(src, SNAP / src.name)
news_snap = SNAP / "news"
news_snap.mkdir(exist_ok=True)
for src in (ROOT/"data"/"news").glob("*.json"):
    shutil.copy2(src, news_snap / src.name)
print(f"📦 Snapshot saved → {SNAP}")
