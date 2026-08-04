#!/usr/bin/env python3
"""Fetch news headlines for each stock via Exa search, save to news/<ticker>.json."""
import json, subprocess, sys, time
from pathlib import Path
from datetime import datetime

ROOT = Path.home() / "hermes_share" / "nvda_chain"
NEWS = ROOT / "data" / "news"
ARCHIVE = ROOT / "data" / "news_archive"
NEWS.mkdir(parents=True, exist_ok=True)
ARCHIVE.mkdir(parents=True, exist_ok=True)
stocks = json.loads((ROOT / "data" / "stocks.json").read_text())["stocks"]


def archive_news(ticker: str, items: list, fetched_at: str):
    """按 URL 去重追加到 news_archive/{ticker}.jsonl"""
    path = ARCHIVE / f'{ticker.replace("/", "_")}.jsonl'
    seen = set()
    if path.exists():
        with path.open() as f:
            for line in f:
                try:
                    seen.add(json.loads(line).get("url"))
                except Exception:
                    pass
    new_count = 0
    with path.open("a") as f:
        for it in items:
            url = it.get("url")
            if not url or url in seen:
                continue
            record = {**it, "first_seen": fetched_at, "ticker": ticker}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            seen.add(url)
            new_count += 1
    return new_count


def exa_search(query: str, num: int = 6):
    """Call mcporter Exa via subprocess, return list of {title, url, published, summary}."""
    # mcporter looks for ./config/mcporter.json — must run from the right cwd
    cwd = str(Path.home())
    cmd = ["mcporter", "--config", str(Path.home() / "config" / "mcporter.json"), "call",
           f'exa.web_search_exa(query: "{query}", num_results: {num})']
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=cwd)
        if r.returncode != 0:
            print(f"  mcporter rc={r.returncode} stderr={r.stderr[:200]}", file=sys.stderr)
            return []
        # parse Title:/URL:/Published:/Highlights: blocks
        items = []
        cur = {}
        in_highlights = False
        for line in r.stdout.splitlines():
            if line.startswith("Title: "):
                if cur.get("title"): items.append(cur)
                cur = {"title": line[7:].strip()}
                in_highlights = False
            elif line.startswith("URL: "):
                cur["url"] = line[5:].strip()
            elif line.startswith("Published: "):
                cur["published"] = line[11:].strip()
            elif line.startswith("Author: "):
                cur["author"] = line[8:].strip()
            elif line.startswith("Highlights:"):
                cur["highlights"] = ""
                in_highlights = True
            elif in_highlights and line.strip() and line.strip() != "---":
                cur["highlights"] = (cur.get("highlights", "") + " " + line.strip())[:600]
        if cur.get("title"): items.append(cur)
        return [i for i in items if i.get("title") and i.get("url")]
    except Exception as e:
        print(f"  ERROR {e}", file=sys.stderr)
        return []


now = datetime.now().isoformat(timespec="seconds")

def main():
    for s in stocks:
        name = s["name"]
        code = s["ticker"]
        if s["market"] == "A股":
            query = f'{name} {code.split(".")[0]} 业绩 订单 合作 AI 算力'
        else:
            query = f'{name} {code} earnings NVIDIA AI supply chain 2026'
        print(f"→ {code} {name}", file=sys.stderr)
        items = exa_search(query, num=6)
        out = {"ticker": code, "name": name, "fetched_at": now, "count": len(items), "items": items}
        (NEWS / f'{code.replace("/", "_")}.json').write_text(json.dumps(out, ensure_ascii=False, indent=2))
        new_n = archive_news(code, items, now)
        print(f"   got {len(items)} items (+{new_n} new to archive)", file=sys.stderr)
        time.sleep(1)
    print("\nDone. News dir:", NEWS, file=sys.stderr)

if __name__ == "__main__":
    main()
