#!/usr/bin/env python3
"""
Post-market analysis: compare today's moves against yesterday's forecast,
generate forward-looking view, persist to history for continuous learning.
"""
import json, sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
ROOT = Path.home() / "hermes_share" / "nvda_chain"
DATA = ROOT / "data"
HISTORY = DATA / "analysis_history.jsonl"

def load_history():
    """Load all past analysis entries."""
    if not HISTORY.exists():
        return []
    entries = []
    for line in HISTORY.read_text().strip().splitlines():
        try:
            entries.append(json.loads(line))
        except:
            pass
    return entries

def get_yesterday_forecast():
    """Get yesterday's forward-looking forecast."""
    entries = load_history()
    if not entries:
        return None
    # Find most recent entry with a forecast
    for e in reversed(entries):
        if e.get("forecast"):
            return e
    return None

def get_today_prices():
    """Load today's prices from prices.json."""
    pf = DATA / "prices.json"
    if not pf.exists():
        return []
    d = json.loads(pf.read_text())
    return d.get("stocks", [])

def get_today_news():
    """Load today's news headlines."""
    news = {}
    for f in (DATA / "news").glob("*.json"):
        try:
            d = json.loads(f.read_text())
            ticker = d.get("ticker", "")
            items = d.get("items", [])
            if items:
                news[ticker] = [it.get("title", "") for it in items[:3]]
        except:
            pass
    return news

def get_prev_closes():
    """Get previous close from price history CSVs."""
    closes = {}
    for csv in (DATA / "prices_history").glob("*.csv"):
        ticker = csv.stem
        lines = csv.read_text().strip().splitlines()
        if len(lines) >= 2:
            try:
                closes[ticker] = float(lines[-1].split(",")[4])
            except:
                pass
    return closes

def main():
    now = datetime.now(CST)
    today = now.strftime("%Y-%m-%d")

    # Only run after 15:30 CST (post-close buffer)
    if now.hour < 15 or (now.hour == 15 and now.minute < 30):
        print("[SILENT] Not yet post-close")
        sys.exit(0)

    prices = get_today_prices()
    if not prices:
        print("[SILENT] No price data")
        sys.exit(0)

    yesterday = get_yesterday_forecast()
    prev_closes = get_prev_closes()
    news = get_today_news()

    # Build today's move summary
    moves = []
    for s in prices:
        t = s.get("ticker", "")
        ret = s.get("returns", {})
        r1d = ret.get("1d")
        r1w = ret.get("1w")
        last = s.get("last_price", 0)
        prev = prev_closes.get(t, 0)

        moves.append({
            "ticker": t,
            "name": s.get("name", ""),
            "sector": s.get("sector", ""),
            "last_price": last,
            "prev_close": prev,
            "daily_pct": r1d,
            "weekly_pct": r1w,
            "news": news.get(t, []),
        })

    # Sort by absolute daily change
    moves.sort(key=lambda x: abs(x.get("daily_pct") or 0), reverse=True)

    # Build analysis payload for LLM
    output = {
        "date": today,
        "timestamp": now.isoformat(),
        "total_stocks": len(moves),
        "moves": moves,
        "yesterday_forecast": yesterday.get("forecast") if yesterday else None,
        "yesterday_date": yesterday.get("date") if yesterday else None,
        "history_entries_count": len(load_history()),
        "up_count": sum(1 for m in moves if (m.get("daily_pct") or 0) > 0),
        "down_count": sum(1 for m in moves if (m.get("daily_pct") or 0) < 0),
        "flat_count": sum(1 for m in moves if (m.get("daily_pct") or 0) == 0),
        "avg_daily_pct": round(sum((m.get("daily_pct") or 0) for m in moves) / len(moves), 2) if moves else 0,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
