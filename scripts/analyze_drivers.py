#!/usr/bin/env python3
"""多驱动 lead-lag 分析 v2：对比 NVDA / 工业富联 / 中际旭创 / 寒武纪 / 海光信息 五种驱动信号
对 25 票池子里其余票的传导强度。

设计:
  - 驱动信号都用「超额收益」(个股 - 本市场基准)
  - A 股驱动 → A 股下游：同日对齐 (lag=0 同一天)
  - NVDA → A 股下游：+1 日错位 (NVDA t 收盘 vs A 股 t+1 收盘)
  - 同链主自己不算
  - 输出:
      drivers_corr_matrix.csv      宽表
      drivers_corr_heatmap.png     5 个驱动并列热力图
      drivers_summary.md           谁带动谁的结论
"""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
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

BENCH = {
    "美股": "SPY", "A股": "_CSI300", "港股": "_HSI",
    "台股": "_TWII", "韩股": "_KS11",
}
ASIA_MARKETS = {"A股", "港股", "台股", "韩股"}

DRIVERS = [
    {"ticker": "NVDA",      "name": "NVDA",         "market": "美股", "label": "NVDA (美股对照)"},
    {"ticker": "601138.SH", "name": "工业富联",     "market": "A股",  "label": "工业富联 (AI服务器链主)"},
    {"ticker": "300308.SZ", "name": "中际旭创",     "market": "A股",  "label": "中际旭创 (光模块链主)"},
    {"ticker": "688256.SH", "name": "寒武纪",       "market": "A股",  "label": "寒武纪 (国产GPU链主)"},
    {"ticker": "688041.SH", "name": "海光信息",     "market": "A股",  "label": "海光信息 (国产CPU链主)"},
]
LAGS = [0, 1, 2, 3]


def load_returns(csv_name: str) -> pd.Series:
    df = pd.read_csv(HIST / f"{csv_name}.csv", parse_dates=["Date"], index_col="Date")
    return df["Close"].pct_change().dropna().rename(csv_name)


def excess(stock_csv: str, bench_csv: str) -> pd.Series:
    s = load_returns(stock_csv); b = load_returns(bench_csv)
    al = pd.concat([s, b], axis=1, join="inner").dropna()
    return (al.iloc[:, 0] - al.iloc[:, 1]).rename(stock_csv)


# 计算每个驱动对每个下游的相关矩阵
all_results = {}  # driver_label -> DataFrame
peak_matrix = {}  # driver_label -> {ticker: best_corr}

for drv in DRIVERS:
    drv_csv = drv["ticker"].replace("/", "_")
    drv_bench = BENCH[drv["market"]]
    driver_series = excess(drv_csv, drv_bench)
    print(f"\n=== Driver: {drv['label']} ({len(driver_series)} 天) ===", file=sys.stderr)

    rows = []
    for s in stocks:
        if s["ticker"] == drv["ticker"]:
            continue  # 跳过链主自己
        down_market = s["market"]
        down_bench = BENCH.get(down_market)
        if not down_bench:
            continue
        down_csv = s["ticker"].replace("/", "_")
        try:
            downstream = excess(down_csv, down_bench)
        except FileNotFoundError:
            continue

        # 跨市场偏移：仅当驱动是美股、下游是亚洲时需要 +1 日
        cross_tz = (drv["market"] == "美股") and (down_market in ASIA_MARKETS)
        base_shift = 1 if cross_tz else 0

        rec = {"ticker": s["ticker"], "name": s["name"],
               "market": down_market, "category": s.get("category", "")}
        for lag in LAGS:
            shifted = downstream.shift(-(base_shift + lag))
            df = pd.concat([driver_series, shifted], axis=1, join="inner").dropna()
            if len(df) < 60:
                rec[f"lag{lag}"] = np.nan; continue
            rec[f"lag{lag}"] = round(df.iloc[:, 0].corr(df.iloc[:, 1]), 3)
        # peak
        corrs = [rec.get(f"lag{l}") for l in LAGS]
        valid = [(l, c) for l, c in zip(LAGS, corrs) if c is not None and not pd.isna(c)]
        if valid:
            peak_lag, peak_corr = max(valid, key=lambda x: abs(x[1]))
            rec["peak_lag"] = peak_lag; rec["peak_corr"] = peak_corr
        rows.append(rec)

    df = pd.DataFrame(rows).sort_values("peak_corr", ascending=False, na_position="last")
    all_results[drv["label"]] = df
    peak_matrix[drv["label"]] = {r["ticker"]: r.get("peak_corr") for _, r in df.iterrows()}
    df.to_csv(OUT / f"drivers_{drv['name']}.csv", index=False)

# 综合矩阵：行=下游 25 票，列=5 个驱动，值=peak_corr
all_tickers = sorted({s["ticker"] for s in stocks})
ticker_name = {s["ticker"]: s["name"] for s in stocks}
ticker_cat = {s["ticker"]: s.get("category", "") for s in stocks}

mat_rows = []
for t in all_tickers:
    row = {"ticker": t, "name": ticker_name[t], "category": ticker_cat[t]}
    for drv in DRIVERS:
        row[drv["name"]] = peak_matrix[drv["label"]].get(t)
    mat_rows.append(row)

mat = pd.DataFrame(mat_rows)
mat.to_csv(OUT / "drivers_corr_matrix.csv", index=False)

# 画总图: 5 列驱动 × 25 行下游, 颜色=peak_corr
fig, ax = plt.subplots(figsize=(7, 11))
data = mat[[d["name"] for d in DRIVERS]].astype(float).values
labels_y = [f"{r['name']} ({r['ticker']})\n[{r['category']}]" for _, r in mat.iterrows()]
labels_x = [d["label"] for d in DRIVERS]

im = ax.imshow(data, cmap="RdBu_r", vmin=-0.5, vmax=0.5, aspect="auto")
ax.set_xticks(range(len(labels_x)))
ax.set_xticklabels(labels_x, rotation=25, ha="right", fontsize=9)
ax.set_yticks(range(len(labels_y)))
ax.set_yticklabels(labels_y, fontsize=7)
for i in range(data.shape[0]):
    for j in range(data.shape[1]):
        v = data[i, j]
        if np.isnan(v):
            ax.text(j, i, "—", ha="center", va="center", color="gray", fontsize=8)
        else:
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    color="white" if abs(v) > 0.35 else "black", fontsize=7)
plt.colorbar(im, ax=ax, label="peak |corr|, 最优 lag 下的 Pearson")
ax.set_title("供应链链主驱动力对比: 谁能真正带动谁?\n(每格为该驱动对该下游在 lag 0/1/2/3 中的最强相关, ~500 交易日, 超额收益, 链主自身为—)",
             fontsize=10)
plt.tight_layout()
plt.savefig(OUT / "drivers_corr_heatmap.png", dpi=140)
print(f"\nSaved {OUT/'drivers_corr_heatmap.png'}", file=sys.stderr)

# === Top 传导对 ===
print("\n=== 每个驱动的 Top-5 下游 (按 |peak_corr| 排序) ===")
for drv in DRIVERS:
    df = all_results[drv["label"]].copy()
    df["abs_peak"] = df["peak_corr"].abs()
    top = df.sort_values("abs_peak", ascending=False).head(5)
    print(f"\n▼ 驱动 = {drv['label']}")
    print(top[["ticker","name","category","lag0","lag1","lag2","lag3","peak_lag","peak_corr"]].to_string(index=False))
