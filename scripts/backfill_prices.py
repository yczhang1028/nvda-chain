#!/usr/bin/env python3
"""一次性回填股票池所有票过去 N 年的日 K 线到 prices_history/{ticker}.csv。
后续日常更新由 fetch_prices.py 自动增量追加。

用法:
    python3 backfill_prices.py [--years 2]
"""
import argparse, json, sys
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import yfinance as yf

ROOT = Path.home() / "hermes_share" / "nvda_chain" / "data"
HIST = ROOT / "prices_history"
HIST.mkdir(parents=True, exist_ok=True)

ap = argparse.ArgumentParser()
ap.add_argument("--years", type=int, default=2)
args = ap.parse_args()

stocks = json.loads((ROOT / "stocks.json").read_text())["stocks"]
yf_codes = [s["yf"] for s in stocks]

today = date.today()
start = today - timedelta(days=args.years * 365 + 30)
print(f"Backfill {len(yf_codes)} tickers: {start} → {today}", file=sys.stderr)

data = yf.download(yf_codes, start=start, end=today + timedelta(days=1),
                   progress=False, auto_adjust=True, threads=True)

ok = skip = 0
for s in stocks:
    yf_code = s["yf"]
    ticker = s["ticker"]
    try:
        if len(yf_codes) == 1:
            df = data[["Open", "High", "Low", "Close", "Volume"]].copy()
        else:
            df = pd.DataFrame({
                "Open":   data["Open"][yf_code],
                "High":   data["High"][yf_code],
                "Low":    data["Low"][yf_code],
                "Close":  data["Close"][yf_code],
                "Volume": data["Volume"][yf_code],
            })
        df = df.dropna(subset=["Close"])
        if df.empty:
            print(f"  SKIP {ticker} (empty)", file=sys.stderr)
            skip += 1
            continue
        df.index = df.index.tz_localize(None) if df.index.tz else df.index
        df.index.name = "Date"
        df = df.round({"Open": 4, "High": 4, "Low": 4, "Close": 4})
        df["Volume"] = df["Volume"].astype("Int64")

        csv_path = HIST / f"{ticker.replace('/', '_')}.csv"
        if csv_path.exists():
            old = pd.read_csv(csv_path, index_col="Date", parse_dates=["Date"])
            merged = pd.concat([old, df])
            merged = merged[~merged.index.duplicated(keep="last")].sort_index()
        else:
            merged = df.sort_index()
        merged.to_csv(csv_path, date_format="%Y-%m-%d")
        ok += 1
        print(f"  OK   {ticker:<12} {s['name']:<10} rows={len(merged)} {merged.index.min().date()} → {merged.index.max().date()}", file=sys.stderr)
    except Exception as e:
        skip += 1
        print(f"  ERR  {ticker}: {e}", file=sys.stderr)

print(f"\nBackfill done. ok={ok} skip={skip}. Files in {HIST}", file=sys.stderr)
