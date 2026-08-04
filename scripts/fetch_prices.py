#!/usr/bin/env python3
"""Pull multi-period returns for the stock pool."""
import json, sys
from datetime import date, timedelta
from pathlib import Path
import yfinance as yf

ROOT = Path.home() / "hermes_share" / "nvda_chain" / "data"
stocks = json.loads((ROOT / "stocks.json").read_text())["stocks"]

today = date.today()
periods = {
    "1w":  today - timedelta(days=7),
    "1m":  today - timedelta(days=30),
    "3m":  today - timedelta(days=90),
    "6m":  today - timedelta(days=180),
    "1y":  today - timedelta(days=365),
}

# yfinance is fastest with batch download
yf_codes = [s["yf"] for s in stocks]
print(f"Fetching {len(yf_codes)} tickers from {today - timedelta(days=400)} to {today}...", file=sys.stderr)
data = yf.download(yf_codes, start=today - timedelta(days=400), end=today + timedelta(days=1),
                   progress=False, auto_adjust=True, threads=True)
closes = data["Close"]
# 同时拿到 OHLCV 用于历史归档
ohlcv_panel = data  # MultiIndex columns: (field, ticker)

out = {"as_of": today.isoformat(), "stocks": []}
for s in stocks:
    yf_code = s["yf"]
    if yf_code not in closes.columns:
        # single-ticker case
        series = closes if hasattr(closes, "iloc") and yf_code == yf_codes[0] and len(yf_codes) == 1 else None
    else:
        series = closes[yf_code].dropna()

    if series is None or len(series) == 0:
        print(f"SKIPPED {yf_code} ({s['name']})", file=sys.stderr)
        continue

    last_price = float(series.iloc[-1])
    last_date = series.index[-1].date()

    entry = {**s, "last_price": round(last_price, 3), "last_date": last_date.isoformat(), "returns": {}}
    for label, start in periods.items():
        # nearest trading day >= start
        window = series[series.index.date >= start]
        if len(window) == 0:
            entry["returns"][label] = None
            continue
        start_price = float(window.iloc[0])
        ret = (last_price / start_price - 1) * 100
        entry["returns"][label] = round(ret, 2)
    out["stocks"].append(entry)
    print(f"OK  {yf_code:<12} {s['name']:<10} last={last_price:>10.2f} 1w={entry['returns'].get('1w')}% 1y={entry['returns'].get('1y')}%", file=sys.stderr)

(ROOT / "prices.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
print(f"\nWrote {ROOT/'prices.json'}", file=sys.stderr)

# === 历史归档：把每只票最近 400 天 OHLCV 合并进 prices_history/{ticker}.csv ===
import pandas as pd
HIST = ROOT / "prices_history"
HIST.mkdir(parents=True, exist_ok=True)

for s in stocks:
    yf_code = s["yf"]
    ticker = s["ticker"]
    try:
        if len(yf_codes) == 1:
            df = data[["Open", "High", "Low", "Close", "Volume"]].copy()
        else:
            # data 是 MultiIndex columns: (field, ticker)
            df = pd.DataFrame({
                "Open":   data["Open"][yf_code],
                "High":   data["High"][yf_code],
                "Low":    data["Low"][yf_code],
                "Close":  data["Close"][yf_code],
                "Volume": data["Volume"][yf_code],
            })
        df = df.dropna(subset=["Close"])
        if df.empty:
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
    except Exception as e:
        print(f"  HIST ERR {ticker}: {e}", file=sys.stderr)

print(f"Wrote OHLCV history → {HIST}", file=sys.stderr)
