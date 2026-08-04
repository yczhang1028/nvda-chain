#!/usr/bin/env python3
"""拉 AMD/Intel/AVGO + 各市场指数到 prices_history/（用于联动分析）。"""
import sys
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import yfinance as yf

HIST = Path.home() / "hermes_share" / "nvda_chain" / "data" / "prices_history"
HIST.mkdir(parents=True, exist_ok=True)

# 上游驱动信号 + 基准指数
EXTRA = {
    "AMD":     "AMD",        # 上游
    "INTC":    "INTC",       # 上游
    "AVGO":    "AVGO",       # 上游（AI 网络）
    "SPY":     "SPY",        # 美股基准
    "_HSI":    "^HSI",       # 港股基准（恒生）
    "_TWII":   "^TWII",      # 台股基准
    "_CSI300": "000300.SS",  # A 股基准（沪深 300）
    "_KS11":   "^KS11",      # 韩股基准
}

today = date.today()
start = today - timedelta(days=2*365 + 30)

codes = list(EXTRA.values())
data = yf.download(codes, start=start, end=today + timedelta(days=1),
                   progress=False, auto_adjust=True, threads=True)

for alias, yf_code in EXTRA.items():
    try:
        df = pd.DataFrame({
            "Open":   data["Open"][yf_code],
            "High":   data["High"][yf_code],
            "Low":    data["Low"][yf_code],
            "Close":  data["Close"][yf_code],
            "Volume": data["Volume"][yf_code],
        }).dropna(subset=["Close"])
        if df.empty:
            print(f"SKIP {alias}", file=sys.stderr); continue
        df.index = df.index.tz_localize(None) if df.index.tz else df.index
        df.index.name = "Date"
        df = df.round({"Open":4,"High":4,"Low":4,"Close":4})
        df["Volume"] = df["Volume"].astype("Int64")
        df.to_csv(HIST / f"{alias}.csv", date_format="%Y-%m-%d")
        print(f"OK  {alias:<10} rows={len(df)} {df.index.min().date()} → {df.index.max().date()}", file=sys.stderr)
    except Exception as e:
        print(f"ERR {alias}: {e}", file=sys.stderr)
