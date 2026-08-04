#!/usr/bin/env python3
"""Render the dashboard HTML from stocks.json + prices.json + news/*.json."""
import json
from pathlib import Path
from datetime import datetime

ROOT = Path.home() / "hermes_share" / "nvda_chain"
DATA = ROOT / "data"
NEWS = DATA / "news"

stocks_meta = {s["ticker"]: s for s in json.loads((DATA / "stocks.json").read_text())["stocks"]}
categories = json.loads((DATA / "stocks.json").read_text())["categories"]
prices_raw = json.loads((DATA / "prices.json").read_text())
# prices stock data is a list under 'stocks' key
prices = {s["ticker"]: s for s in prices_raw.get("stocks", [])}
as_of = prices_raw.get("as_of", datetime.now().strftime("%Y-%m-%d"))
news_by_ticker = {}
if NEWS.exists():
    for f in NEWS.glob("*.json"):
        try:
            d = json.loads(f.read_text())
            news_by_ticker[d["ticker"]] = d
        except Exception:
            pass

# upstream theme feeds
upstream = {}
upstream_file = DATA / "upstream_feeds.json"
if upstream_file.exists():
    raw = json.loads(upstream_file.read_text())
    upstream = raw.get("feeds", {})

def fmt_ret(v):
    if v is None: return '<span class="muted">—</span>'
    cls = "up" if v > 0 else ("down" if v < 0 else "flat")
    sign = "+" if v > 0 else ""
    return f'<span class="ret {cls}">{sign}{v:.1f}%</span>'

def render_news(ticker):
    n = news_by_ticker.get(ticker)
    if not n or not n.get("items"):
        return '<div class="news-empty">暂无新闻</div>'
    items = n["items"][:4]
    rows = []
    for it in items:
        title = (it.get("title") or "")[:90]
        url = it.get("url", "#")
        pub = (it.get("published") or "")[:10]
        rows.append(f'<a class="news-item" href="{url}" target="_blank"><span class="news-date">{pub}</span><span class="news-title">{title}</span></a>')
    return "".join(rows)

def render_upstream():
    if not upstream:
        return ""
    blocks = []
    for feed_id, feed in upstream.items():
        items = feed.get("items", [])[:8]
        if not items:
            continue
        cat_color = feed.get("color", "#64748b")
        rows = []
        for it in items:
            title = it.get("title", "")[:90]
            url = it.get("url", "#")
            hl = it.get("highlight", "")[:120]
            pub_date = (it.get("published") or "N/A")[:10]
            rows.append(f'<a class="up-item" href="{url}" target="_blank"><div class="up-date">{pub_date}</div><div class="up-text"><div class="up-title">{title}</div><div class="up-hl">{hl}</div></div></a>')
        count = len(items)
        blocks.append(
            f'<div class="up-block" style="--c:{cat_color}">'
            f'<div class="up-header">{feed["label"]} <span class="up-count">{count} 条</span></div>'
            f'{"".join(rows)}'
            f'</div>'
        )
    if not blocks:
        return ""
    return f'<section class="upstream"><div class="up-grid">{"".join(blocks)}</div></section>'

# Build stock rows
stock_list = sorted(stocks_meta.items(), key=lambda x: (
    {"S": 0, "A": 1, "REF": 2}.get(x[1].get("tier", "REF"), 9),
    x[0]
))

rows = []
for ticker, meta in stock_list:
    p = prices.get(ticker, {})
    tier = meta.get("tier", "A")
    colors = {"S": "#ef4444", "A": "#f59e0b", "REF": "#475569"}
    tier_color = colors.get(tier, "#64748b")
    cat = meta.get("category", "")
    cat_color = categories.get(cat, "#64748b")

    # Returns
    rets = p.get("returns", {})
    ret_1w = fmt_ret(rets.get("1w"))
    ret_1m = fmt_ret(rets.get("1m"))
    ret_3m = fmt_ret(rets.get("3m"))
    ret_6m = fmt_ret(rets.get("6m"))
    ret_1y = fmt_ret(rets.get("1y"))
    price = p.get("last_price")
    price_str = f"{price:.2f}" if price is not None else "—"

    # Meta details
    role = meta.get("role", "")
    coverage = meta.get("coverage", "")
    tags_html = "".join(f'<span class="tag">{t}</span>' for t in meta.get("tags", []))

    rows.append(f"""    <details class="row">
      <summary>
        <div class="col-tier"><span class="tier" style="background:{tier_color}">{tier}</span></div>
        <div class="col-name">
          <div class="ticker">{ticker}</div>
          <div class="name">{meta["name"]}</div>
        </div>
        <div class="col-cat"><span class="cat" style="--c:{cat_color}">{cat}</span></div>
        <div class="col-price">{price_str}</div>
        <div class="col-ret">{ret_1w}</div>
        <div class="col-ret">{ret_1m}</div>
        <div class="col-ret">{ret_3m}</div>
        <div class="col-ret">{ret_6m}</div>
        <div class="col-ret">{ret_1y}</div>
      </summary>
      <div class="detail">
        <div class="meta">
          <div><b>供应链角色：</b>{role}</div>
          <div><b>覆盖机构：</b>{coverage}</div>
          <div class="tags">{tags_html}</div>
        </div>
        <div class="news-section">
          <div class="news-header">📰 最新新闻</div>
          {render_news(ticker)}
        </div>
      </div>
    </details>""")

CSS = """<style>
:root {
  --bg: #0b0f19;
  --surface: #111827;
  --border: #1e293b;
  --text: #e2e8f0;
  --heading: #f1f5f9;
  --muted: #64748b;
  --up: #ef4444; --down: #10b981; --flat: #94a3b8;
  --accent: #38bdf8;
  --radius: 8px;
  --font-sans: -apple-system, 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  --font-mono: 'SF Mono', 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace;
}
* { box-sizing: border-box; margin: 0; }
body {
  margin: 0; font-family: var(--font-sans);
  background: var(--bg); color: var(--text);
  padding: 24px 28px;
  -webkit-font-smoothing: antialiased;
}
header {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 20px; flex-wrap: wrap; gap: 8px;
}
h1 { font-size: 20px; font-weight: 600; color: var(--heading); letter-spacing: -0.02em; }
.subtitle { color: var(--muted); font-size: 12px; font-weight: 400; margin-top: 4px; }
.legend {
  display: flex; gap: 12px; flex-wrap: wrap; align-items: center;
  font-size: 11px; color: var(--muted); margin-bottom: 16px;
  padding: 10px 14px; background: var(--surface);
  border: 1px solid var(--border); border-radius: var(--radius);
}
.legend .tier-pill {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 10px; border-radius: 6px;
  font-size: 10px; font-weight: 700; color: #fff;
}
.table {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}
.head, summary {
  display: grid;
  grid-template-columns: 50px 1.6fr 1fr 0.8fr 0.7fr 0.7fr 0.7fr 0.7fr 0.7fr;
  gap: 10px; padding: 11px 16px; align-items: center;
}
.head {
  background: #0f1320; color: var(--muted);
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 10;
}
summary {
  cursor: pointer; border-bottom: 1px solid var(--border);
  font-size: 13px; list-style: none;
  transition: background 0.15s;
}
summary::-webkit-details-marker { display: none; }
summary:hover { background: rgba(255,255,255,0.03); }
.tier {
  display: inline-flex; align-items: center; justify-content: center;
  width: 26px; height: 26px; border-radius: 6px;
  font-size: 11px; color: white; font-weight: 700;
}
.ticker {
  font-family: var(--font-mono); font-size: 11px; color: var(--muted);
  font-feature-settings: "tnum"; letter-spacing: 0.02em;
}
.name { font-weight: 600; color: var(--text); font-size: 13px; }
.cat {
  display: inline-block; padding: 3px 10px; border-radius: 5px;
  font-size: 11px; font-weight: 500;
  background: color-mix(in srgb, var(--c) 16%, transparent);
  color: var(--c);
  border: 1px solid color-mix(in srgb, var(--c) 30%, transparent);
}
.col-price {
  font-family: var(--font-mono); text-align: right;
  font-size: 12px; font-feature-settings: "tnum";
}
.col-ret {
  text-align: right; font-family: var(--font-mono);
  font-size: 12px; font-feature-settings: "tnum"; font-weight: 500;
}
.ret.up   { color: var(--up); }
.ret.down { color: var(--down); }
.ret.flat { color: var(--flat); }
.muted { color: var(--muted); }
.detail {
  padding: 0 16px 16px 16px;
  background: #0c1019;
  font-size: 12px;
}
.meta > div { margin: 6px 0; }
.tags { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
.tag {
  background: rgba(56, 189, 248, 0.1);
  color: #7dd3fc;
  padding: 2px 9px; border-radius: 4px;
  font-size: 11px; font-weight: 500;
}
.news-section { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border); }
.news-header { color: var(--muted); font-size: 11px; font-weight: 600; margin-bottom: 8px; }
.news-item {
  display: flex; gap: 10px; padding: 5px 0;
  color: #cbd5e1; text-decoration: none;
  border-bottom: 1px solid #1e293b;
  transition: color 0.15s;
}
.news-item:hover { color: var(--accent); }
.news-date {
  color: var(--muted); font-family: var(--font-mono);
  font-size: 10px; min-width: 72px;
}
.news-title { flex: 1; font-size: 12px; line-height: 1.5; }
.news-empty { color: var(--muted); font-size: 11px; }
.upstream { margin-bottom: 20px; }
.up-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.up-block {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--c);
  border-radius: var(--radius);
  padding: 14px 16px;
}
.up-header {
  font-weight: 600; color: var(--c); font-size: 13px;
  margin-bottom: 10px; display: flex; align-items: baseline; gap: 6px;
}
.up-count { color: var(--muted); font-weight: 400; font-size: 11px; }
.up-item {
  display: flex; gap: 10px; padding: 6px 0;
  color: #cbd5e1; text-decoration: none;
  border-bottom: 1px solid #1e293b;
  transition: color 0.15s;
}
.up-item:last-child { border-bottom: none; }
.up-item:hover .up-title { color: var(--c); }
.up-date {
  color: var(--muted); font-family: var(--font-mono);
  font-size: 10px; min-width: 72px; padding-top: 2px;
}
.up-title { font-size: 12px; font-weight: 500; margin-bottom: 2px; line-height: 1.4; }
.up-hl { color: var(--muted); font-size: 11px; line-height: 1.4; }
@media (max-width: 900px) {
  .up-grid { grid-template-columns: 1fr; }
}
footer {
  margin-top: 20px; padding: 14px;
  color: var(--muted); font-size: 11px;
  text-align: center;
  border-top: 1px solid var(--border);
}
@media (max-width: 900px) {
  body { padding: 16px; }
  .head, summary {
    grid-template-columns: 40px 1fr 0.7fr 0.7fr 0.7fr 0.7fr;
    gap: 6px; padding: 10px 12px; font-size: 11px;
  }
  .col-cat, .col-ret:nth-child(7), .col-ret:nth-child(8) { display: none; }
}
</style>"""

html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NVIDIA Rubin 供应链 · A股跟踪看板</title>
{CSS}</head><body>
<header>
  <div>
    <h1>NVIDIA Rubin 供应链 · A股跟踪看板</h1>
    <div class="subtitle">15只 A 股精选 + 5只海外参照 · 数据截至 {as_of}</div>
  </div>
  <div class="subtitle">生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
</header>
<div class="legend">
  <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
    推荐等级：
    <span class="tier-pill" style="background:#ef4444">S 投行点名+独家卡位</span>
    <span class="tier-pill" style="background:#f59e0b;color:#1e293b">A 主流投行覆盖</span>
    <span class="tier-pill" style="background:#475569">REF 海外参照</span>
    <span style="margin-left:8px">· 涨红跌绿（A股习惯）</span>
    <span>· 点击行展开详情</span>
  </div>
</div>
{render_upstream()}
<div class="table">
  <div class="head">
    <div>等级</div><div>名称</div><div>板块</div><div>现价</div>
    <div>1周</div><div>1月</div><div>3月</div><div>6月</div><div>1年</div>
  </div>
  {''.join(rows)}
</div>
<footer>数据：yfinance（价格） + Agent Reach/Exa（新闻） · 自动更新中</footer>
</body></html>"""

(ROOT / "index.html").write_text(html)
print(f"Wrote {ROOT/'index.html'} ({len(html):,} bytes)")
