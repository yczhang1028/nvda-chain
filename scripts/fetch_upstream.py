#!/usr/bin/env python3
"""Fetch upstream narrative feeds: NVIDIA roadmap/news + China inference chip industry news."""
import json, subprocess, sys, time
from pathlib import Path
from datetime import datetime

ROOT = Path.home() / "hermes_share" / "nvda_chain"
DATA = ROOT / "data"

# Theme feeds: each has a list of queries; results merged
FEEDS = {
    "nvidia_动向": {
        "label": "🔺 NVIDIA 上游动向",
        "color": "#22d3ee",
        "queries": [
            "NVIDIA Rubin Vera CPU roadmap 2026 production",
            "NVIDIA China export control H20 Blackwell ban",
            "Jensen Huang keynote announcement supply chain 2026",
            "NVIDIA HBM4 CoWoS capacity 2026 shipment",
        ],
    },
    "国产推理卡": {
        "label": "🇨🇳 国产 AI 芯片动向",
        "color": "#f472b6",
        "queries": [
            "华为昇腾 910C 910D 国产 AI 芯片 2026 出货",
            "寒武纪 思元 590 690 推理卡 订单 2026",
            "海光 深算 DCU 国产 AI 算力 中科曙光 2026",
            "壁仞 燧原 摩尔线程 国产 GPU 量产 2026",
        ],
    },
}

def exa_search(query: str, num: int = 5):
    cwd = str(Path.home())
    cmd = ["mcporter", "--config", str(Path.home() / "config" / "mcporter.json"), "call",
           f'exa.web_search_exa(query: "{query}", num_results: {num})']
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=cwd)
        if r.returncode != 0:
            return []
        items, cur, in_h = [], {}, False
        for line in r.stdout.splitlines():
            if line.startswith("Title: "):
                if cur.get("title"): items.append(cur)
                cur = {"title": line[7:].strip()}
                in_h = False
            elif line.startswith("URL: "):
                cur["url"] = line[5:].strip()
            elif line.startswith("Published: "):
                cur["published"] = line[11:].strip()
            elif line.startswith("Highlights:"):
                cur["highlights"] = ""
                in_h = True
            elif in_h and line.strip() and line.strip() != "---":
                cur["highlights"] = (cur.get("highlights","") + " " + line.strip())[:400]
        if cur.get("title"): items.append(cur)
        return [i for i in items if i.get("title") and i.get("url")]
    except Exception:
        return []


now = datetime.now().isoformat(timespec="seconds")
out = {"fetched_at": now, "feeds": {}}

for key, feed in FEEDS.items():
    all_items = []
    seen_urls = set()
    print(f"\n=== {feed['label']} ===", file=sys.stderr)
    for q in feed["queries"]:
        print(f"  → {q[:60]}", file=sys.stderr)
        items = exa_search(q, num=5)
        for it in items:
            if it["url"] in seen_urls: continue
            seen_urls.add(it["url"])
            all_items.append(it)
        time.sleep(1)
    # sort by published date desc (fall back to insertion order)
    def sort_key(it):
        p = it.get("published","")
        return p if p else ""
    all_items.sort(key=sort_key, reverse=True)
    out["feeds"][key] = {
        "label": feed["label"],
        "color": feed["color"],
        "count": len(all_items),
        "items": all_items[:15],  # cap each feed
    }
    print(f"  → {len(all_items)} unique items", file=sys.stderr)

(DATA / "upstream_feeds.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
print(f"\nWrote {DATA/'upstream_feeds.json'}", file=sys.stderr)
