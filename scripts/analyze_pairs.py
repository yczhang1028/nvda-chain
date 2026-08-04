#!/usr/bin/env python3
"""滚动 60 日相关性时序 + 配对交易残差 Z-score
针对核心 5 对配对:
  - 中际旭创 ↔ 新易盛  (光模块同板块)
  - 中际旭创 ↔ 天孚通信
  - 工业富联 ↔ 沪电股份  (链主-PCB)
  - 工业富联 ↔ 胜宏科技
  - 寒武纪   ↔ 海光信息  (国产算力孪生)
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

PAIRS = [
    ("300308.SZ", "中际旭创", "300502.SZ", "新易盛",   "光模块"),
    ("300308.SZ", "中际旭创", "300394.SZ", "天孚通信", "光模块"),
    ("601138.SH", "工业富联", "002463.SZ", "沪电股份", "AI服务器→PCB"),
    ("601138.SH", "工业富联", "300476.SZ", "胜宏科技", "AI服务器→PCB"),
    ("688256.SH", "寒武纪",   "688041.SH", "海光信息", "国产算力孪生"),
]

WINDOW = 60
ZWIN = 60      # 残差 Z-score 用 60 日均值/标准差

def load_close(ticker: str) -> pd.Series:
    df = pd.read_csv(HIST / f"{ticker}.csv", parse_dates=["Date"], index_col="Date")
    return df["Close"]

def load_ret(ticker: str) -> pd.Series:
    return load_close(ticker).pct_change().dropna().rename(ticker)

bench = load_ret("_CSI300")

# === 1. 滚动相关性 ===
fig, axes = plt.subplots(len(PAIRS), 1, figsize=(11, 12), sharex=True)
roll_results = []
for ax, (a_t, a_n, b_t, b_n, label) in zip(axes, PAIRS):
    ra = load_ret(a_t); rb = load_ret(b_t)
    # 超额收益
    df = pd.concat([ra, rb, bench], axis=1, join="inner").dropna()
    df.columns = ["a", "b", "bench"]
    df["ea"] = df["a"] - df["bench"]
    df["eb"] = df["b"] - df["bench"]
    roll = df["ea"].rolling(WINDOW).corr(df["eb"]).dropna()
    ax.plot(roll.index, roll.values, color="#c0392b", lw=1.5)
    ax.axhline(roll.mean(), color="gray", ls="--", lw=0.8, label=f"均值 {roll.mean():.2f}")
    ax.fill_between(roll.index, roll.mean()-roll.std(), roll.mean()+roll.std(), color="gray", alpha=0.1)
    ax.set_title(f"{a_n} ↔ {b_n} ({label}) · 60日滚动相关 · 当前 {roll.iloc[-1]:.2f}", fontsize=10)
    ax.set_ylim(-0.2, 1.0)
    ax.grid(alpha=0.3)
    ax.legend(loc="lower left", fontsize=8)
    roll_results.append({
        "pair": f"{a_n}↔{b_n}", "label": label,
        "current": round(roll.iloc[-1], 3),
        "mean": round(roll.mean(), 3),
        "min": round(roll.min(), 3),
        "max": round(roll.max(), 3),
        "trend_3m": round(roll.iloc[-1] - roll.iloc[-60], 3) if len(roll) >= 60 else None,
    })
plt.tight_layout()
plt.savefig(OUT / "rolling_corr.png", dpi=130)
print(f"Saved {OUT/'rolling_corr.png'}", file=sys.stderr)

pd.DataFrame(roll_results).to_csv(OUT / "rolling_corr_summary.csv", index=False)

# === 2. 配对残差 Z-score ===
# 模型: log(P_b) = α + β·log(P_a) + ε   |  在滚动窗口内估计 β, 取残差标准化
fig2, axes2 = plt.subplots(len(PAIRS), 1, figsize=(11, 13), sharex=True)
zscores_now = []
for ax, (a_t, a_n, b_t, b_n, label) in zip(axes2, PAIRS):
    pa = np.log(load_close(a_t)); pb = np.log(load_close(b_t))
    df = pd.concat([pa, pb], axis=1, join="inner").dropna()
    df.columns = ["la", "lb"]
    # 滚动 OLS β
    cov = df["la"].rolling(ZWIN).cov(df["lb"])
    var = df["la"].rolling(ZWIN).var()
    beta = cov / var
    alpha = df["lb"].rolling(ZWIN).mean() - beta * df["la"].rolling(ZWIN).mean()
    resid = df["lb"] - (alpha + beta * df["la"])
    z = (resid - resid.rolling(ZWIN).mean()) / resid.rolling(ZWIN).std()
    z = z.dropna()

    ax.plot(z.index, z.values, color="#2c3e50", lw=1)
    ax.axhline(0, color="black", lw=0.5)
    ax.axhline(2, color="#27ae60", ls="--", lw=0.8, label="+2σ (做空 b 做多 a)")
    ax.axhline(-2, color="#e74c3c", ls="--", lw=0.8, label="-2σ (做多 b 做空 a)")
    ax.fill_between(z.index, -1, 1, color="gray", alpha=0.1)
    ax.set_title(f"{a_n} ↔ {b_n} 配对残差 Z-score · 当前 {z.iloc[-1]:.2f}σ", fontsize=10)
    ax.set_ylim(-4, 4)
    ax.grid(alpha=0.3)
    ax.legend(loc="lower left", fontsize=8)
    zscores_now.append({
        "pair": f"{a_n}↔{b_n}", "label": label,
        "z_now": round(z.iloc[-1], 2),
        "signal": "做多 b/做空 a" if z.iloc[-1] < -2 else ("做空 b/做多 a" if z.iloc[-1] > 2 else "—"),
        "abs_z_max_3m": round(z.tail(60).abs().max(), 2),
    })
plt.tight_layout()
plt.savefig(OUT / "pair_zscores.png", dpi=130)
print(f"Saved {OUT/'pair_zscores.png'}", file=sys.stderr)

pd.DataFrame(zscores_now).to_csv(OUT / "pair_signals.csv", index=False)

print("\n=== Rolling Corr Summary ===")
print(pd.DataFrame(roll_results).to_string(index=False))
print("\n=== Pair Z-scores (latest) ===")
print(pd.DataFrame(zscores_now).to_string(index=False))
