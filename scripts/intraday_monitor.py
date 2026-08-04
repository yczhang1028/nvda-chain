#!/usr/bin/env python3
"""
Intraday monitor: fetch latest prices, compare to previous close,
detect significant moves, output structured data for LLM analysis.
Only outputs when something interesting happens (>2% intraday move).
"""
import json, subprocess, sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
ROOT = Path.home() / "hermes_share" / "nvda_chain"
DATA = ROOT / "data"

# Check if within A-share trading hours (Beijing time)
now = datetime.now(CST)
hour, minute = now.hour, now.minute
trading = False
session_label = ""

if now.weekday() >= 5:  # Weekend
    print("[SILENT]")
    sys.exit(0)

# Morning: 9:15-11:30, Afternoon: 12:55-15:05
if 9 <= hour < 11 or (hour == 11 and minute <= 30):
    trading = True
    session_label = "盘中(上午)"
elif hour == 12 and minute >= 55:
    trading = True
    session_label = "盘中(下午开盘)"
elif 13 <= hour < 15:
    trading = True
    session_label = "盘中(下午)"
elif hour == 15 and minute <= 5:
    trading = True
    session_label = "收盘"

if not trading:
    print("[SILENT]")
    sys.exit(0)

# Load stocks list
stocks = json.loads((DATA / "stocks.json").read_text())["stocks"]

# Load previous close from prices_history (last row of each CSV)
prev_close = {}
for s in stocks:
    ticker = s["ticker"]
    csv_path = DATA / "prices_history" / f"{ticker.replace('/', '_')}.csv"
    if csv_path.exists():
        lines = csv_path.read_text().strip().splitlines()
        if len(lines) >= 2:
            last = lines[-1].split(",")
            try:
                prev_close[ticker] = float(last[4])  # Close column
            except (ValueError, IndexError):
                pass

# Fetch current prices via yfinance
import yfinance as yf
tickers_str = " ".join(s["ticker"] for s in stocks)
print(f"Fetching intraday for {len(stocks)} tickers...", file=sys.stderr)

current = {}
try:
    data = yf.download(
        [s["ticker"] for s in stocks],
        period="1d", interval="1m",
        progress=False, auto_adjust=True, group_by="ticker"
    )
    for s in stocks:
        t = s["ticker"]
        try:
            if len(stocks) == 1:
                df = data
            else:
                df = data[t]
            if df.empty:
                continue
            last_row = df.dropna(subset=["Close"]).iloc[-1]
            current[t] = {
                "price": round(float(last_row["Close"]), 2),
                "high": round(float(df["High"].dropna().max()), 2),
                "low": round(float(df["Low"].dropna().min()), 2),
                "volume": int(df["Volume"].dropna().sum()),
            }
        except Exception:
            pass
except Exception as e:
    print(f"yfinance error: {e}", file=sys.stderr)

# If yfinance failed for most, try fallback (daily data)
if len(current) < len(stocks) // 2:
    print("Fallback to daily data...", file=sys.stderr)
    try:
        data2 = yf.download(
            [s["ticker"] for s in stocks],
            period="2d", interval="1d",
            progress=False, auto_adjust=True, group_by="ticker"
        )
        for s in stocks:
            t = s["ticker"]
            if t in current:
                continue
            try:
                if len(stocks) == 1:
                    df = data2
                else:
                    df = data2[t]
                if df.empty:
                    continue
                last_row = df.dropna(subset=["Close"]).iloc[-1]
                current[t] = {
                    "price": round(float(last_row["Close"]), 2),
                    "high": round(float(last_row["High"]), 2),
                    "low": round(float(last_row["Low"]), 2),
                    "volume": int(last_row["Volume"]),
                }
            except Exception:
                pass
    except Exception as e:
        print(f"Fallback error: {e}", file=sys.stderr)

# Compute moves
moves = []
for s in stocks:
    t = s["ticker"]
    if t not in current or t not in prev_close:
        continue
    pc = prev_close[t]
    cp = current[t]["price"]
    if pc == 0:
        continue
    pct = round((cp - pc) / pc * 100, 2)
    moves.append({
        "ticker": t,
        "name": s["name"],
        "sector": s.get("sector", ""),
        "prev_close": pc,
        "current": cp,
        "pct_change": pct,
        "high": current[t]["high"],
        "low": current[t]["low"],
        "volume": current[t]["volume"],
    })

# Sort by absolute change
moves.sort(key=lambda x: abs(x["pct_change"]), reverse=True)

# Filter: only report if any stock moved >2% intraday
significant = [m for m in moves if abs(m["pct_change"]) >= 2.0]

if not significant:
    # Check for overall market pattern (>60% stocks same direction, avg >1%)
    up = [m for m in moves if m["pct_change"] > 0]
    down = [m for m in moves if m["pct_change"] < 0]
    avg_pct = sum(m["pct_change"] for m in moves) / len(moves) if moves else 0
    if (len(up) > len(moves) * 0.6 or len(down) > len(moves) * 0.6) and abs(avg_pct) > 1.0:
        # Market-wide pattern
        pass
    else:
        print("[SILENT]")
        sys.exit(0)

# Load recent news headlines for context
recent_news = []
news_dir = DATA / "news"
for f in news_dir.glob("*.json"):
    try:
        d = json.loads(f.read_text())
        for item in d.get("items", [])[:3]:
            recent_news.append({
                "ticker": d.get("ticker", ""),
                "title": item.get("title", ""),
                "published": item.get("published", ""),
            })
    except:
        pass

# Output structured data for LLM
output = {
    "timestamp": now.isoformat(),
    "session": session_label,
    "total_stocks": len(moves),
    "significant_moves": significant,
    "all_moves": moves,
    "recent_news_count": len(recent_news),
    "recent_news_sample": recent_news[:10],
}
print(json.dumps(output, ensure_ascii=False, indent=2))
