#!/usr/bin/env python3
"""Lead-lag 联动分析 v1.

设计：
  - 驱动信号: NVDA（默认） / AMD / INTC / AVGO
  - 对每只下游票，算它的日收益 vs 驱动信号日收益在 lag=0/1/2/3 的 Pearson 相关
  - 用「超额收益」= 个股收益 − 所属市场基准收益（去掉 β 共同部分）
  - 跨时区对齐：
      美股 -> A 股、港股、台股、韩股 的反应需要 +1 个交易日（驱动 t 收盘 vs 下游 t+1 收盘）
      美股 -> 美股 直接同日
    所以 "lag=0" 的语义：
      对美股下游 = 同一日
      对亚洲下游 = 驱动 t 日 vs 下游 t+1 日（实际是亚洲的"下一个交易日"）
    后续 lag=1/2/3 在此基础上再各 +1 天

输出:
  analysis/leadlag_results.csv   每只票 × 每个 lag 的相关系数
  analysis/leadlag_heatmap.png   热力图
  analysis/leadlag_summary.md    简短结论
"""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
# 加中文字体
for f in ["/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"]:
    try: fm.fontManager.addfont(f)
    except Exception: pass
plt.rcParams["font.sans-serif"] = ["WenQuanYi Zen Hei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path.home() / "hermes_share" / "nvda_chain" / "data"
HIST = ROOT / "prices_history"
OUT = Path.home() / "hermes_share" / "nvda_chain" / "analysis"
OUT.mkdir(parents=True, exist_ok=True)

stocks = json.loads((ROOT / "stocks.json").read_text())["stocks"]

# 市场 -> 基准指数文件名
BENCH = {
    "美股":   "SPY",
    "A股":    "_CSI300",
    "港股":   "_HSI",
    "台股":   "_TWII",
    "韩股":   "_KS11",
}
# 美股之外都视为亚洲（需要 +1 日错位对齐美股）
ASIA_MARKETS = {"A股", "港股", "台股", "韩股"}

DRIVER = "NVDA"          # 主信号
LAGS = [0, 1, 2, 3]


def load_returns(ticker_csv: str) -> pd.Series:
    df = pd.read_csv(HIST / f"{ticker_csv}.csv", parse_dates=["Date"], index_col="Date")
    return df["Close"].pct_change().dropna().rename(ticker_csv)


def excess_return(stock_csv: str, bench_csv: str) -> pd.Series:
    s = load_returns(stock_csv)
    b = load_returns(bench_csv)
    aligned = pd.concat([s, b], axis=1, join="inner").dropna()
    return (aligned.iloc[:, 0] - aligned.iloc[:, 1]).rename(stock_csv)


def driver_excess() -> pd.Series:
    return excess_return(DRIVER, BENCH["美股"])


driver = driver_excess()
print(f"Driver {DRIVER} (excess vs SPY): {len(driver)} 天, "
      f"{driver.index.min().date()} → {driver.index.max().date()}", file=sys.stderr)

rows = []
for s in stocks:
    ticker = s["ticker"]
    market = s["market"]
    bench = BENCH.get(market)
    if not bench:
        continue
    csv_name = ticker.replace("/", "_")
    try:
        downstream = excess_return(csv_name, bench)
    except FileNotFoundError:
        print(f"  SKIP {ticker} no csv", file=sys.stderr); continue

    is_asia = market in ASIA_MARKETS
    # 时区基础偏移
    base_shift = 1 if is_asia else 0

    rec = {"ticker": ticker, "name": s["name"], "market": market,
           "category": s.get("category", ""), "tier": s.get("tier", "")}
    for lag in LAGS:
        # 让下游 series 整体往前 shift -(base_shift+lag) 天与驱动对齐
        shifted_down = downstream.shift(-(base_shift + lag))
        df = pd.concat([driver, shifted_down], axis=1, join="inner").dropna()
        if len(df) < 60:
            rec[f"lag{lag}"] = np.nan
            rec[f"n{lag}"] = len(df)
            continue
        corr = df.iloc[:, 0].corr(df.iloc[:, 1])
        rec[f"lag{lag}"] = round(corr, 3)
        rec[f"n{lag}"] = len(df)
    # 选出 |corr| 最大的 lag 作为该票的「peak lag」
    corrs = [rec.get(f"lag{l}") for l in LAGS]
    if all(c is not None and not pd.isna(c) for c in corrs):
        peak_idx = int(np.argmax([abs(c) for c in corrs]))
        rec["peak_lag"] = LAGS[peak_idx]
        rec["peak_corr"] = corrs[peak_idx]
    rows.append(rec)

df = pd.DataFrame(rows).sort_values("peak_corr", ascending=False, na_position="last")
df.to_csv(OUT / "leadlag_results.csv", index=False)
print(f"\nSaved {OUT/'leadlag_results.csv'}", file=sys.stderr)
print(df[["ticker","name","market","category","lag0","lag1","lag2","lag3","peak_lag","peak_corr"]].to_string(index=False))

# === 热力图 ===
fig, ax = plt.subplots(figsize=(8, 11))
hm = df.set_index(df["name"] + " (" + df["ticker"] + ")")[[f"lag{l}" for l in LAGS]]
hm = hm.dropna()
im = ax.imshow(hm.values, cmap="RdBu_r", vmin=-0.5, vmax=0.5, aspect="auto")
ax.set_xticks(range(len(LAGS)))
ax.set_xticklabels([f"lag={l}d" for l in LAGS])
ax.set_yticks(range(len(hm.index)))
ax.set_yticklabels(hm.index, fontsize=8)
for i in range(hm.shape[0]):
    for j in range(hm.shape[1]):
        v = hm.values[i, j]
        ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                color="white" if abs(v) > 0.3 else "black", fontsize=7)
plt.colorbar(im, ax=ax, label=f"corr(excess_returns, {DRIVER}_excess)")
ax.set_title(f"Lead-lag: 25 supply-chain stocks vs {DRIVER}\n"
             f"(Pearson corr of excess daily returns, ~500 trading days, Asia markets t+1-aligned)",
             fontsize=10)
plt.tight_layout()
plt.savefig(OUT / "leadlag_heatmap.png", dpi=140)
print(f"Saved {OUT/'leadlag_heatmap.png'}", file=sys.stderr)

# === 事件响应分析：NVDA 超额收益大于 +2% / 小于 -2% 的日子，下游平均反应 ===
THRESHOLD = 0.02
up_days   = driver[driver >  THRESHOLD].index
down_days = driver[driver < -THRESHOLD].index
print(f"\n=== Event days: NVDA excess >+2%: {len(up_days)} 天, <-2%: {len(down_days)} 天 ===", file=sys.stderr)

event_rows = []
for s in stocks:
    ticker = s["ticker"]; market = s["market"]
    bench = BENCH.get(market)
    if not bench: continue
    csv_name = ticker.replace("/", "_")
    try:
        downstream = excess_return(csv_name, bench)
    except FileNotFoundError:
        continue
    is_asia = market in ASIA_MARKETS
    base_shift = 1 if is_asia else 0

    rec = {"ticker": ticker, "name": s["name"], "category": s.get("category", "")}
    for lag in LAGS:
        shifted_down = downstream.shift(-(base_shift + lag))
        # 对齐到驱动事件日
        up_resp   = shifted_down.reindex(up_days).dropna()
        down_resp = shifted_down.reindex(down_days).dropna()
        rec[f"up_lag{lag}"]   = round(up_resp.mean()*100, 2)   if len(up_resp)   else None
        rec[f"down_lag{lag}"] = round(down_resp.mean()*100, 2) if len(down_resp) else None
    event_rows.append(rec)

ev = pd.DataFrame(event_rows)
# 按 lag0 的"上涨日响应"排序
ev = ev.sort_values("up_lag0", ascending=False, na_position="last")
ev.to_csv(OUT / "leadlag_events.csv", index=False)
print(f"Saved {OUT/'leadlag_events.csv'}", file=sys.stderr)

print("\n=== NVDA 超额涨 >2% 当日（亚洲为 +1 交易日）下游平均超额响应 (%) ===")
print(ev[["ticker","name","category","up_lag0","up_lag1","up_lag2","up_lag3"]].to_string(index=False))
print("\n=== NVDA 超额跌 <-2% 当日（亚洲为 +1 交易日）下游平均超额响应 (%) ===")
ev2 = ev.sort_values("down_lag0", ascending=True, na_position="last")
print(ev2[["ticker","name","category","down_lag0","down_lag1","down_lag2","down_lag3"]].to_string(index=False))
