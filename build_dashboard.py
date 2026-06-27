#!/usr/bin/env python3
"""
Generates dashboard_0388.html — self-contained interactive HKEX valuation dashboard.
Reads: data/dashboard_data.json   Writes: dashboard_0388.html
"""
import sys, os, json
sys.stdout.reconfigure(encoding="utf-8")

BASE = r"D:\Backup D\Weekly\USB drive\Invest\AI invest\388"
DATA = os.path.join(BASE, "data")

with open(os.path.join(DATA, "dashboard_data.json"), "r", encoding="utf-8") as f:
    D = json.load(f)

# Clip all time-series to 2000-01-01
CUT = "2000-01-01"
for key, s in D["series"].items():
    pairs = [(d, v) for d, v in zip(s["dates"], s["values"]) if d >= CUT]
    if pairs:
        D["series"][key]["dates"]  = [p[0] for p in pairs]
        D["series"][key]["values"] = [p[1] for p in pairs]

meta  = D["meta"]
mc    = D["model_constants"]
pf    = D["prefill"]
fut   = D["futures"]

js_data = json.dumps(D, separators=(",", ":"))

cp     = meta["current_price"]
cd     = meta["current_date"]
tgt    = meta["analyst_target_mean"]
tgt_lo = meta["analyst_target_low"]
tgt_hi = meta["analyst_target_high"]
n_anal = meta["analyst_n"]
ttm    = meta["ttm_eps"]
fwd    = meta["fwd_eps"]
c_hibor= meta["consensus_hibor"]

pe_low    = mc["PE_LOW"]
pe_med    = mc["PE_MEDIAN"]
pe_high   = mc["PE_HIGH"]
ttm_pe    = round(cp / ttm, 1)

# Futures table rows
fut_rows = ""
for label, v in fut.items():
    fut_rows += f"<tr><td>{label}</td><td>{v['ff']:.2f}%</td><td>{v['hibor']:.2f}%</td></tr>"

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HKEX 0388.HK · Valuation Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f0f2f5;color:#1a1a2e;font-size:14px}}

/* HEADER */
.hdr{{background:linear-gradient(135deg,#1A2E4A 0%,#0d1f33 100%);color:#fff;padding:14px 24px;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}}
.hdr-logo{{font-size:20px;font-weight:800;letter-spacing:1px}}
.hdr-logo span{{color:#E8000D}}
.hdr-price .big{{font-size:26px;font-weight:700}}
.hdr-price .sub{{font-size:11px;opacity:.75;margin-top:2px}}
.hdr-meta{{text-align:right;font-size:11px;opacity:.8;line-height:1.8}}

/* LAYOUT */
.main{{display:grid;grid-template-columns:320px 1fr;gap:14px;padding:14px;max-width:1280px;margin:0 auto}}
@media(max-width:860px){{.main{{grid-template-columns:1fr}}}}

/* CARDS */
.card{{background:#fff;border-radius:10px;box-shadow:0 1px 6px rgba(0,0,0,.09);padding:16px}}
.card-title{{font-size:11px;font-weight:700;letter-spacing:1.2px;color:#888;text-transform:uppercase;margin-bottom:12px;border-bottom:2px solid #f0f2f5;padding-bottom:7px}}

/* INPUT PANEL */
.inputs-panel{{display:flex;flex-direction:column;gap:12px}}

/* COLOR-CODED INPUT GROUPS */
.input-group{{background:#fff;border-radius:10px;box-shadow:0 1px 6px rgba(0,0,0,.09);padding:13px 14px;border-left:5px solid #ddd}}
.ig-A{{border-left-color:#1976D2}}
.ig-B{{border-left-color:#D32F2F}}
.ig-C{{border-left-color:#7B1FA2}}
.ig-D{{border-left-color:#F57C00}}

.ig-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:9px}}
.ig-label{{font-weight:700;font-size:12px}}
.ig-A .ig-label{{color:#1976D2}}
.ig-B .ig-label{{color:#D32F2F}}
.ig-C .ig-label{{color:#7B1FA2}}
.ig-D .ig-label{{color:#F57C00}}

.ig-tag{{font-size:10px;font-weight:700;padding:2px 7px;border-radius:3px;color:#fff}}
.ig-A .ig-tag{{background:#1976D2}}
.ig-B .ig-tag{{background:#D32F2F}}
.ig-C .ig-tag{{background:#7B1FA2}}
.ig-D .ig-tag{{background:#F57C00}}

.slider-row{{display:flex;align-items:center;gap:6px;margin-bottom:5px}}
.slider-row input[type=range]{{flex:1;height:4px;cursor:pointer}}
.ig-A input[type=range]{{accent-color:#1976D2}}
.ig-B input[type=range]{{accent-color:#D32F2F}}
.ig-C input[type=range]{{accent-color:#7B1FA2}}
.ig-D input[type=range]{{accent-color:#F57C00}}
.slider-row input[type=number]{{width:70px;border:1.5px solid #ddd;border-radius:5px;padding:4px 5px;font-size:13px;font-weight:700;text-align:center;color:#1A2E4A}}
.slider-row input[type=number]:focus{{outline:none}}
.ig-A input[type=number]:focus{{border-color:#1976D2}}
.ig-B input[type=number]:focus{{border-color:#D32F2F}}
.ig-C input[type=number]:focus{{border-color:#7B1FA2}}
.ig-D input[type=number]:focus{{border-color:#F57C00}}
.slider-row .unit{{font-size:11px;color:#888;min-width:22px}}
.slider-min,.slider-max{{font-size:11px;color:#bbb;min-width:28px}}
.ig-hints{{display:flex;justify-content:space-between;font-size:11px;color:#999}}

/* HIBOR FUTURES PANEL */
.futures-mini{{background:#f5f8ff;border-radius:6px;padding:8px 10px;margin-top:8px;font-size:11px}}
.futures-mini table{{width:100%;border-collapse:collapse}}
.futures-mini td{{padding:2px 4px;color:#444}}
.futures-mini td:last-child{{text-align:right;font-weight:700;color:#D32F2F}}

/* P/E STATS PANEL */
.pe-stats{{background:#fafafa;border-radius:6px;padding:8px 10px;margin-top:8px;font-size:11px}}
.pe-stats-row{{display:flex;justify-content:space-between;align-items:center;padding:3px 0}}
.pe-stats-row.sep{{border-top:1px solid #eee;margin-top:3px;padding-top:6px}}
.pe-stat-label{{color:#666}}
.pe-stat-val{{font-weight:700;min-width:40px;text-align:right}}
.pe-stat-val.low{{color:#D32F2F}}
.pe-stat-val.mid{{color:#1A2E4A;font-size:13px}}
.pe-stat-val.high{{color:#2e7d32}}
.pe-stat-val.current{{color:#555}}
.pe-active-note{{font-size:10px;color:#1976D2;font-style:italic;margin-left:4px}}

/* ANALYST PANEL */
.analyst-row{{display:flex;gap:8px}}
.analyst-card{{flex:1;background:#fff;border-radius:7px;padding:10px 12px;border-left:3px solid #f39c12;box-shadow:0 1px 4px rgba(0,0,0,.07)}}
.analyst-card .ac-val{{font-size:17px;font-weight:800;color:#1A2E4A}}
.analyst-card .ac-label{{font-size:10px;color:#999;margin-top:1px}}

/* RIGHT PANEL */
.right-panel{{display:flex;flex-direction:column;gap:12px}}

/* REVENUE TABLE */
.rev-table{{width:100%;border-collapse:collapse;font-size:13px}}
.rev-table td,.rev-table th{{padding:5px 6px;border-bottom:1px solid #f5f5f5;vertical-align:middle}}
.rev-table td:nth-child(2),.rev-table th:nth-child(2){{text-align:right;font-weight:600;font-variant-numeric:tabular-nums}}
.rev-table td:nth-child(3),.rev-table th:nth-child(3){{text-align:right;font-size:11px;color:#aaa;min-width:56px;font-weight:400}}
.rev-table th{{font-size:10px;font-weight:700;color:#bbb;text-transform:uppercase;border-bottom:2px solid #eee;padding-bottom:6px}}
/* Colored variable rows */
.rev-table tr.rv-A td:first-child{{border-left:3px solid #1976D2;padding-left:8px;color:#1565C0}}
.rev-table tr.rv-B td:first-child{{border-left:3px solid #D32F2F;padding-left:8px;color:#B71C1C}}
.rev-table tr.rv-C td:first-child{{border-left:3px solid #7B1FA2;padding-left:8px;color:#6A1B9A}}
.rev-table tr.rv-A td:nth-child(2){{color:#1565C0}}
.rev-table tr.rv-B td:nth-child(2){{color:#B71C1C}}
.rev-table tr.rv-C td:nth-child(2){{color:#6A1B9A}}
.rev-table tr.rv-A td:nth-child(3){{color:#1976D2}}
.rev-table tr.rv-B td:nth-child(3){{color:#D32F2F}}
.rev-table tr.rv-C td:nth-child(3){{color:#7B1FA2}}
.rev-table tr.fixed-row td{{color:#aaa}}
.rev-table tr.sep td{{border-top:2px solid #ddd;padding-top:7px;font-weight:700}}
.rev-table tr.opex td{{color:#c0392b}}
.rev-table tr.profit td{{font-weight:700;color:#27ae60;font-size:14px}}
.rev-table tr.eps-row td{{font-weight:800;font-size:15px;color:#1A2E4A;border-top:2px solid #1A2E4A;padding-top:7px}}
.rev-table tr.analyst-eps td{{font-size:12px;color:#666;background:#fafafa}}
.pct-pos{{color:#2e7d32!important;font-weight:600!important}}
.pct-neg{{color:#c0392b!important;font-weight:600!important}}

/* VALUATION GRID */
.val-grid{{display:grid;grid-template-columns:1fr 1.2fr 1fr;gap:10px;margin-bottom:12px}}
.val-scenario{{text-align:center;padding:11px 5px;border-radius:8px}}
.val-scenario.bear{{background:#fff5f5;border:1.5px solid #ffcccc}}
.val-scenario.fair{{background:#f0f7ff;border:2px solid #1A2E4A}}
.val-scenario.bull{{background:#f0fff5;border:1.5px solid #b7e4c7}}
.val-scenario .pe-tag{{font-size:10px;color:#888;font-weight:600}}
.val-scenario .val-price{{font-size:21px;font-weight:800;margin:3px 0}}
.val-scenario.bear .val-price{{color:#D32F2F}}
.val-scenario.fair .val-price{{color:#1A2E4A}}
.val-scenario.bull .val-price{{color:#2e7d32}}
.val-scenario .val-ud{{font-size:11px;font-weight:600}}

/* RANGE BAR */
.range-container{{margin:4px 0 10px;position:relative;padding-top:50px}}
.range-label{{display:flex;justify-content:space-between;font-size:10px;color:#bbb;margin-bottom:3px}}
.range-track{{height:7px;background:#f0f0f0;border-radius:4px;position:relative}}
.range-fill{{height:100%;background:linear-gradient(90deg,#ffd5d5,#ddeeff,#d5f5d5);border-radius:4px;position:absolute;left:0;right:0}}
.marker{{position:absolute;top:-5px;width:3px;height:18px;border-radius:2px;transform:translateX(-50%)}}
.mk-current{{background:#333;z-index:3}}
.mk-fair{{background:#1A2E4A;z-index:2}}
.mk-target{{background:#f39c12;z-index:1}}
.marker-label{{position:absolute;top:22px;transform:translateX(-50%);font-size:9px;white-space:nowrap;font-weight:600;text-align:center}}
.marker-label-above{{position:absolute;bottom:22px;transform:translateX(-50%);font-size:9px;white-space:nowrap;font-weight:600;text-align:center}}

/* STATUS BANNER */
.status-banner{{padding:9px 13px;border-radius:6px;font-size:12px;font-weight:600;display:flex;justify-content:space-between;align-items:center}}
.status-banner.underval{{background:#e8f5e9;color:#1b5e20}}
.status-banner.fairval{{background:#e3f2fd;color:#0d47a1}}
.status-banner.overval{{background:#fce4ec;color:#880e4f}}

/* REV BADGE (colored square, matches sidebar labels) */
.rev-badge{{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:3px;font-size:10px;font-weight:800;color:#fff;margin-right:5px;vertical-align:middle;flex-shrink:0}}
.rev-badge.bA{{background:#1976D2}}
.rev-badge.bB{{background:#D32F2F}}
.rev-badge.bC{{background:#7B1FA2}}

/* CHART SECTION */
#mainChart{{max-height:280px}}
.chart-section{{max-width:1280px;margin:0 auto 18px;padding:0 14px}}
.chart-tabs{{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap}}
.chart-tab{{padding:6px 14px;border-radius:5px;border:1.5px solid #ddd;background:#fff;cursor:pointer;font-size:12px;font-weight:600;color:#777;transition:all .15s}}
.chart-tab:hover{{border-color:#1A2E4A;color:#1A2E4A}}
.chart-tab.active{{background:#1A2E4A;color:#fff;border-color:#1A2E4A}}
.chart-tab.t-A{{border-left:3px solid #1976D2}}
.chart-tab.t-B{{border-left:3px solid #D32F2F}}
.chart-tab.t-C{{border-left:3px solid #7B1FA2}}
.chart-tab.t-D{{border-left:3px solid #F57C00}}
.chart-tab.active.t-A,.chart-tab.active.t-B,.chart-tab.active.t-C,.chart-tab.active.t-D{{border-left-width:3px}}
.chart-wrapper{{background:#fff;border-radius:10px;box-shadow:0 1px 6px rgba(0,0,0,.09);padding:16px}}
.chart-desc{{font-size:11px;color:#aaa;margin-top:5px;text-align:center}}

/* MODEL NOTES */
.model-note{{font-size:12px;color:#666;line-height:1.7}}
.footer{{text-align:center;font-size:11px;color:#bbb;padding:10px;max-width:1280px;margin:0 auto}}
</style>
</head>
<body>

<!-- HEADER -->
<div class="hdr">
  <div class="hdr-logo">HKEX <span>0388.HK</span> &nbsp; Valuation Dashboard</div>
  <div class="hdr-price">
    <div class="big">HKD {cp:.0f}</div>
    <div class="sub">Latest close: {cd}</div>
    <div class="sub" style="color:#7abaff;margin-top:3px;font-size:10px">Auto-updated monthly (1st) &nbsp;·&nbsp; Last refresh: {meta['generated']}</div>
  </div>
  <div class="hdr-meta">
    <div>{n_anal} analysts &nbsp;|&nbsp; Target: <strong>HKD {tgt:.0f}</strong> ({tgt_lo:.0f}–{tgt_hi:.0f})</div>
    <div>TTM EPS: <strong>HKD {ttm:.2f}</strong> &nbsp;|&nbsp; Fwd EPS: <strong>HKD {fwd:.2f}</strong> &nbsp;|&nbsp; TTM P/E: <strong>{ttm_pe}x</strong></div>
    <div style="color:#aaa;font-size:10px">Model: Rev – Fixed OpEx (HKD 9bn) = Net Profit ÷ 1,267mn shares = EPS × P/E = Price</div>
  </div>
</div>

<!-- MAIN -->
<div class="main">

  <!-- LEFT: INPUTS -->
  <div class="inputs-panel">

    <!-- A: ADT -->
    <div class="input-group ig-A">
      <div class="ig-header">
        <span class="ig-label">&#x24B6; Average Daily Turnover — ADT (HKD bn/day)</span>
        <span class="ig-tag">A</span>
      </div>
      <div class="slider-row">
        <span class="slider-min">50</span>
        <input type="range" id="sl-adt" min="50" max="500" step="5" value="{pf['adt']:.0f}" oninput="syncNum('adt')">
        <span class="slider-max">500</span>
        <input type="number" id="in-adt" value="{pf['adt']:.0f}" min="50" max="500" step="5" oninput="syncSlider('adt')">
        <span class="unit">bn</span>
      </div>
      <div class="ig-hints">
        <span>2024A: 120bn &nbsp;|&nbsp; 2025A: 249.8bn</span>
        <span>2026E: <strong>{pf['adt']:.0f}bn</strong></span>
      </div>
    </div>

    <!-- B: HIBOR -->
    <div class="input-group ig-B">
      <div class="ig-header">
        <span class="ig-label">&#x24B7; HIBOR / Avg Funding Rate (%)</span>
        <span class="ig-tag">B</span>
      </div>
      <div class="slider-row">
        <span class="slider-min">0.5</span>
        <input type="range" id="sl-hibor" min="0.5" max="8" step="0.1" value="{pf['hibor']}" oninput="syncNum('hibor')">
        <span class="slider-max">8%</span>
        <input type="number" id="in-hibor" value="{pf['hibor']}" min="0.5" max="8" step="0.1" oninput="syncSlider('hibor')">
        <span class="unit">%</span>
      </div>
      <div class="ig-hints">
        <span>Futures consensus: ~{c_hibor:.1f}% full-yr avg</span>
        <span>Peak 2023: ~5.7%</span>
      </div>
      <div class="futures-mini">
        <div style="font-weight:700;margin-bottom:4px;color:#1A2E4A">Live ZQ Fed Funds Futures</div>
        <table>
          <tr style="color:#999"><td>Contract</td><td>Fed Funds</td><td style="text-align:right">Est. HIBOR</td></tr>
          {fut_rows}
        </table>
        <div style="margin-top:4px;color:#777;font-size:10px">HIBOR ≈ FF −40bps. Futures imply rates hold/rise in 2H 2026.</div>
      </div>
    </div>

    <!-- C: IPO -->
    <div class="input-group ig-C">
      <div class="ig-header">
        <span class="ig-label">&#x24B8; IPO Proceeds (HKD bn / year)</span>
        <span class="ig-tag">C</span>
      </div>
      <div class="slider-row">
        <span class="slider-min">0</span>
        <input type="range" id="sl-ipo" min="0" max="500" step="10" value="{pf['ipo']:.0f}" oninput="syncNum('ipo')">
        <span class="slider-max">500</span>
        <input type="number" id="in-ipo" value="{pf['ipo']:.0f}" min="0" max="500" step="10" oninput="syncSlider('ipo')">
        <span class="unit">bn</span>
      </div>
      <div class="ig-hints">
        <span>2023A: 46bn &nbsp;|&nbsp; 2024A: 87bn &nbsp;|&nbsp; 2025A: ~80bn</span>
        <span>Peak 2010: 449bn</span>
      </div>
    </div>

    <!-- D: P/E -->
    <div class="input-group ig-D">
      <div class="ig-header">
        <span class="ig-label">&#x24B9; P/E Multiple (x) — sets Fair case</span>
        <span class="ig-tag">D</span>
      </div>
      <div class="slider-row">
        <span class="slider-min">15</span>
        <input type="range" id="sl-pe" min="15" max="55" step="0.5" value="{pf['pe']:.1f}" oninput="syncNum('pe')">
        <span class="slider-max">55</span>
        <input type="number" id="in-pe" value="{pf['pe']:.1f}" min="15" max="55" step="0.5" oninput="syncSlider('pe')">
        <span class="unit">x</span>
      </div>
      <div class="pe-stats">
        <div class="pe-stats-row">
          <span class="pe-stat-label">Current TTM P/E</span>
          <span class="pe-stat-val current">{ttm_pe}x</span>
        </div>
        <div class="pe-stats-row sep">
          <span class="pe-stat-label">Bear: Historical Low (25th pct)</span>
          <span class="pe-stat-val low">{pe_low:.1f}x</span>
        </div>
        <div class="pe-stats-row">
          <span class="pe-stat-label">Median (2015+) <span class="pe-active-note">← model default</span></span>
          <span class="pe-stat-val mid">{pe_med:.1f}x</span>
        </div>
        <div class="pe-stats-row">
          <span class="pe-stat-label">Bull: Historical High (75th+)</span>
          <span class="pe-stat-val high">{pe_high:.1f}x</span>
        </div>
        <div class="pe-stats-row" style="margin-top:4px;border-top:1px solid #eee;padding-top:5px">
          <span class="pe-stat-label">Analyst implied fwd P/E</span>
          <span class="pe-stat-val" style="color:#f39c12">{tgt/fwd:.1f}x</span>
        </div>
      </div>
    </div>

    <!-- Analyst Summary -->
    <div class="card">
      <div class="card-title">Analyst Consensus &nbsp;<span style="font-weight:400;color:#bbb">({n_anal} analysts)</span></div>
      <div class="analyst-row">
        <div class="analyst-card" style="border-color:#D32F2F">
          <div class="ac-val" style="color:#D32F2F">HKD {tgt_lo:.0f}</div>
          <div class="ac-label">Low Target</div>
        </div>
        <div class="analyst-card">
          <div class="ac-val">HKD {tgt:.0f}</div>
          <div class="ac-label">Mean Target (+{(tgt/cp-1)*100:.0f}%)</div>
        </div>
        <div class="analyst-card" style="border-color:#2e7d32">
          <div class="ac-val" style="color:#2e7d32">HKD {tgt_hi:.0f}</div>
          <div class="ac-label">High Target</div>
        </div>
      </div>
    </div>

  </div>

  <!-- RIGHT: REVENUE + VALUATION -->
  <div class="right-panel">

    <!-- Revenue Model -->
    <div class="card">
      <div class="card-title">Revenue Model &nbsp;<span style="font-weight:400;color:#aaa">2026E (HKD mn) — live calculation</span></div>
      <table class="rev-table">
        <tr><th>Line Item</th><th>HKD mn</th><th>%</th></tr>
        <tr class="rv-A">
          <td><span class="rev-badge bA">A</span>Trading + Clearing &nbsp;<span style="font-size:10px;color:#aaa">(ADT × ~250 days × blended fee)</span></td>
          <td id="rv-trading">--</td>
          <td id="rv-trading-pct">--</td>
        </tr>
        <tr class="rv-B">
          <td><span class="rev-badge bB">B</span>Investment NII &nbsp;<span style="font-size:10px;color:#aaa">(HIBOR × HKD 270bn clearing pool)</span></td>
          <td id="rv-nii">--</td>
          <td id="rv-nii-pct">--</td>
        </tr>
        <tr class="rv-C">
          <td><span class="rev-badge bC">C</span>Listing / IPO Fees &nbsp;<span style="font-size:10px;color:#aaa">(620 fixed + 0.8% of IPO proceeds)</span></td>
          <td id="rv-listing">--</td>
          <td id="rv-listing-pct">--</td>
        </tr>
        <tr class="fixed-row">
          <td>&nbsp;&nbsp;&nbsp; Market Data + Connectivity</td>
          <td>1,050</td>
          <td id="rv-data-pct">--</td>
        </tr>
        <tr class="fixed-row">
          <td>&nbsp;&nbsp;&nbsp; Other (LME, Depository)</td>
          <td>1,100</td>
          <td id="rv-other-pct">--</td>
        </tr>
        <tr class="sep">
          <td>Total Revenue</td>
          <td id="rv-total">--</td>
          <td style="color:#bbb">100%</td>
        </tr>
        <tr class="opex">
          <td>Operating Expenses &nbsp;<span style="font-size:10px">(staff, IT, LME — approx. fixed)</span></td>
          <td>(9,000)</td>
          <td id="rv-opex-pct">--</td>
        </tr>
        <tr class="profit">
          <td>Net Profit</td>
          <td id="rv-profit">--</td>
          <td id="rv-margin" style="color:#27ae60;font-size:12px">--</td>
        </tr>
        <tr class="eps-row">
          <td>EPS — Model &nbsp;<span style="font-size:11px;font-weight:400;color:#888">(1,267mn shares)</span></td>
          <td id="rv-eps">--</td>
          <td id="rv-eps-pct" style="font-size:11px;white-space:nowrap">--</td>
        </tr>
        <tr class="analyst-eps">
          <td>&nbsp;&nbsp;EPS — Analyst Fwd &nbsp;<span style="font-size:10px;color:#bbb">({n_anal} analysts)</span></td>
          <td style="color:#f39c12;font-weight:700">HKD {fwd:.2f}</td>
          <td style="color:#bbb;font-size:10px">consensus</td>
        </tr>
      </table>
    </div>

    <!-- Valuation Output -->
    <div class="card">
      <div class="card-title">Valuation &nbsp;<span id="val-subtitle" style="font-weight:400;color:#aaa">EPS × P/E Band</span></div>
      <div class="val-grid">
        <div class="val-scenario bear">
          <div class="pe-tag">BEAR &nbsp;P/E {pe_low:.0f}x</div>
          <div class="val-price" id="v-low">--</div>
          <div class="val-ud" id="v-low-ud" style="color:#D32F2F"></div>
        </div>
        <div class="val-scenario fair">
          <div class="pe-tag">FAIR &nbsp;P/E <span id="pe-label-mid">--</span>x</div>
          <div class="val-price" id="v-fair">--</div>
          <div class="val-ud" id="v-fair-ud" style="color:#1A2E4A"></div>
        </div>
        <div class="val-scenario bull">
          <div class="pe-tag">BULL &nbsp;P/E {pe_high:.0f}x</div>
          <div class="val-price" id="v-high">--</div>
          <div class="val-ud" id="v-high-ud" style="color:#2e7d32"></div>
        </div>
      </div>

      <div class="range-container">
        <div class="range-label">
          <span id="rng-lo">--</span>
          <span>← Valuation Range →</span>
          <span id="rng-hi">--</span>
        </div>
        <div class="range-track" id="range-track">
          <div class="range-fill"></div>
          <div class="marker mk-current" id="mk-current" style="left:40%">
            <div class="marker-label-above" style="color:#333">▲ Now<br>HKD {cp:.0f}</div>
          </div>
          <div class="marker mk-fair" id="mk-fair" style="left:55%">
            <div class="marker-label" style="color:#1A2E4A">● Fair</div>
          </div>
          <div class="marker mk-target" id="mk-target" style="left:75%">
            <div class="marker-label-above" style="color:#f39c12;bottom:44px">◆ Analyst<br>HKD {tgt:.0f}</div>
          </div>
        </div>
      </div>

      <div class="status-banner fairval" id="status-banner">
        <span id="status-text">Calculating…</span>
        <span id="status-updown"></span>
      </div>
    </div>

    <!-- Model Notes -->
    <div class="card">
      <div class="card-title">Model Notes</div>
      <div class="model-note">
        <p><strong>Range logic:</strong> Low / Fair / High use the <em>same model EPS</em> from inputs A–C, multiplied by historical P/E trough ({pe_low:.0f}x), user-selected P/E, and peak ({pe_high:.0f}x). Revenue risk is captured by moving sliders; the range purely reflects market re-rating risk.</p>
        <p style="margin-top:8px"><strong>ADT surge 2025:</strong> 249.8bn/day vs 120bn in 2024 reflects the China stimulus + AI rally. TRADING_K recalibrated to 47.2 (= 11,800mn ÷ 249.8bn) vs 88 in earlier years — fee mix shifted.</p>
        <p style="margin-top:8px"><strong>Fixed OpEx ~HKD 9bn/year</strong> (staff, IT, LME). All incremental NII and trading revenue flow almost entirely to EPS — this is why net margin rose from 54% (2022) to ~71% (2025) as volumes and rates surged.</p>
        <p style="margin-top:8px;font-size:11px;color:#bbb">Generated: {meta['generated']} · yfinance, FRED, HKEX annual reports</p>
      </div>
    </div>

  </div>
</div>

<!-- CHART SECTION -->
<div class="chart-section">
  <div class="chart-tabs">
    <button class="chart-tab active" id="tab-price" onclick="showChart('price',this)">&#x1F4C8; HKEX Price</button>
    <button class="chart-tab t-A" id="tab-adt"   onclick="showChart('adt',this)">&#x24B6; ADT</button>
    <button class="chart-tab t-B" id="tab-hibor" onclick="showChart('hibor',this)">&#x24B7; HIBOR</button>
    <button class="chart-tab t-C" id="tab-ipo"   onclick="showChart('ipo',this)">&#x24B8; IPO Proceeds</button>
    <button class="chart-tab t-D" id="tab-pe"    onclick="showChart('pe',this)">&#x24B9; P/E History</button>
  </div>
  <div class="chart-wrapper">
    <canvas id="mainChart" height="270"></canvas>
    <div class="chart-desc" id="chart-desc"></div>
  </div>
</div>

<div class="footer">
  HKEX (0388.HK) Valuation Dashboard · For reference only, not investment advice ·
  Data: yfinance, FRED, HKEX annual reports · 2026 figures are estimates
</div>

<script>
const D = {js_data};
const M = D.model_constants;
const CURRENT_PRICE  = D.meta.current_price;
const ANALYST_TARGET = D.meta.analyst_target_mean;
const FWD_EPS        = D.meta.fwd_eps;
const PE_LOW         = M.PE_LOW;
const PE_HIGH        = M.PE_HIGH;

// ── CALCULATION ──────────────────────────────────────────────
function calc(adt, hibor, ipo, pe) {{
  const trading  = adt   * M.TRADING_K;
  const nii      = hibor * M.NII_K;
  const listing  = M.IPO_BASE + ipo * M.IPO_K;
  const total    = trading + nii + listing + M.DATA_REV + M.OTHER_REV;
  const profit   = total - M.OPEX;
  const eps      = profit / M.SHARES_MN;
  const margin   = profit / total * 100;
  return {{
    trading, nii, listing, total, profit, eps, margin,
    priceFair:  eps * pe,
    priceLow:   eps * PE_LOW,
    priceHigh:  eps * PE_HIGH,
  }};
}}

// ── SYNC ─────────────────────────────────────────────────────
function syncNum(k) {{
  document.getElementById("in-" + k).value = document.getElementById("sl-" + k).value;
  update();
}}
function syncSlider(k) {{
  document.getElementById("sl-" + k).value = document.getElementById("in-" + k).value;
  update();
}}
function getVal(k) {{ return parseFloat(document.getElementById("in-" + k).value) || 0; }}

function fmt(v, dp=0) {{
  return v == null ? "--" : v.toLocaleString("en-HK", {{minimumFractionDigits:dp, maximumFractionDigits:dp}});
}}
function upd(price, ref) {{ return (price / ref - 1) * 100; }}
function pctStr(v) {{ return (v > 0 ? "+" : "") + fmt(v, 1) + "%"; }}

// ── MAIN UPDATE ───────────────────────────────────────────────
function update() {{
  const adt   = getVal("adt");
  const hibor = getVal("hibor");
  const ipo   = getVal("ipo");
  const pe    = getVal("pe");
  const r     = calc(adt, hibor, ipo, pe);

  document.getElementById("rv-trading").textContent = fmt(r.trading);
  document.getElementById("rv-nii").textContent     = fmt(r.nii);
  document.getElementById("rv-listing").textContent = fmt(r.listing);
  document.getElementById("rv-total").textContent   = fmt(r.total);
  document.getElementById("rv-profit").textContent  = fmt(r.profit);
  document.getElementById("rv-eps").textContent     = "HKD " + fmt(r.eps, 2);
  document.getElementById("rv-margin").textContent  = fmt(r.margin, 1) + "% margin";

  // Revenue % breakdown column
  const p = (v) => (v / r.total * 100).toFixed(1) + "%";
  document.getElementById("rv-trading-pct").textContent = p(r.trading);
  document.getElementById("rv-nii-pct").textContent     = p(r.nii);
  document.getElementById("rv-listing-pct").textContent = p(r.listing);
  document.getElementById("rv-data-pct").textContent    = p(M.DATA_REV);
  document.getElementById("rv-other-pct").textContent   = p(M.OTHER_REV);
  document.getElementById("rv-opex-pct").textContent    = "(" + p(M.OPEX) + ")";

  // EPS vs analyst % diff
  const epsDiff = (r.eps / FWD_EPS - 1) * 100;
  const epsEl = document.getElementById("rv-eps-pct");
  epsEl.textContent = (epsDiff >= 0 ? "+" : "") + epsDiff.toFixed(1) + "% vs analyst";
  epsEl.className   = epsDiff >= 0 ? "pct-pos" : "pct-neg";

  document.getElementById("pe-label-mid").textContent = fmt(pe, 1);
  document.getElementById("val-subtitle").textContent  = "EPS  HKD " + fmt(r.eps, 2) + "  ×  P/E Band";

  document.getElementById("v-low").textContent  = "HKD " + fmt(r.priceLow);
  document.getElementById("v-fair").textContent = "HKD " + fmt(r.priceFair);
  document.getElementById("v-high").textContent = "HKD " + fmt(r.priceHigh);
  document.getElementById("v-low-ud").textContent  = pctStr(upd(r.priceLow,  CURRENT_PRICE)) + " vs now";
  document.getElementById("v-fair-ud").textContent = pctStr(upd(r.priceFair, CURRENT_PRICE)) + " vs now";
  document.getElementById("v-high-ud").textContent = pctStr(upd(r.priceHigh, CURRENT_PRICE)) + " vs now";

  // Range bar — extend right edge to include analyst target
  const lo = r.priceLow * 0.85, hi = Math.max(r.priceHigh, ANALYST_TARGET) * 1.08;
  const span = hi - lo;
  const pos = (v) => Math.max(1, Math.min(99, (v - lo) / span * 100)) + "%";
  document.getElementById("rng-lo").textContent = "HKD " + fmt(r.priceLow);
  document.getElementById("rng-hi").textContent = "HKD " + fmt(Math.max(r.priceHigh, ANALYST_TARGET));
  document.getElementById("mk-current").style.left = pos(CURRENT_PRICE);
  document.getElementById("mk-fair").style.left    = pos(r.priceFair);
  document.getElementById("mk-target").style.left  = pos(ANALYST_TARGET);

  // Status
  const du = upd(r.priceFair, CURRENT_PRICE);
  const banner = document.getElementById("status-banner");
  let cls, txt;
  if (r.priceFair > CURRENT_PRICE * 1.10) {{
    cls="underval"; txt="UNDERVALUED vs Fair — current price below fair value on these inputs";
  }} else if (r.priceFair < CURRENT_PRICE * 0.90) {{
    cls="overval";  txt="OVERVALUED vs Fair — current price above fair value on these inputs";
  }} else {{
    cls="fairval";  txt="NEAR FAIR VALUE — current price in line with model output";
  }}
  banner.className = "status-banner " + cls;
  document.getElementById("status-text").textContent   = txt;
  document.getElementById("status-updown").textContent = "Fair: HKD " + fmt(r.priceFair) + " (" + pctStr(du) + " vs current)";

  if (currentChart === "price" && mainChart) updatePriceBands(r);
}}

// ── CHARTS ───────────────────────────────────────────────────
let mainChart    = null;
let currentChart = "price";

const CHART_META = {{
  price: {{
    color:"#1A2E4A", fill:"rgba(26,46,74,0.06)", type:"line", tension:0.3,
    label:"0388.HK Close (HKD)", yLabel:"HKD",
    desc:"HKEX (0388.HK) monthly closing price since listing (Jun 2000). Dashed lines = current model valuation bands (Bear/Fair/Bull) and analyst target — update in real time as you adjust sliders.",
  }},
  adt: {{
    color:"#1976D2", fill:"rgba(25,118,210,0.8)", type:"bar", tension:0,
    label:"ADT (HKD bn/day)", yLabel:"HKD bn/day",
    desc:"HK market Average Daily Turnover (ADT) by year (HKD bn/day). Source: HKEX annual results & reports. 2025A = 249.8bn (confirmed). 2026 = Jan–May YTD estimate (lighter bar).",
  }},
  hibor: {{
    color:"#D32F2F", fill:"rgba(211,47,47,0.06)", type:"line", tension:0.3,
    label:"3M HIBOR / Funding Rate (%)", yLabel:"%",
    desc:"3-month HIBOR proxied from US Fed Funds rate −40bps (HKD peg). Source: FRED. Dashed red line = your current slider input.",
  }},
  ipo: {{
    color:"#7B1FA2", fill:"rgba(123,31,162,0.08)", type:"bar", tension:0,
    label:"IPO Proceeds (HKD bn/yr)", yLabel:"HKD bn",
    desc:"Total IPO funds raised on HKEX each year (HKD bn). Source: HKEX annual statistics. 2026 is an estimate.",
  }},
  pe: {{
    color:"#F57C00", fill:"rgba(245,124,0,0.07)", type:"line", tension:0.3,
    label:"HKEX Trailing P/E (x)", yLabel:"P/E (x)",
    desc:"HKEX (0388.HK) trailing P/E: monthly close ÷ interpolated annual EPS. Dashed lines = Bear ({pe_low:.0f}x) and Bull ({pe_high:.0f}x) historical P/E bands. Source: HKEX annual reports.",
  }},
}};

function buildChart(key) {{
  const cfg = CHART_META[key];
  const s   = D.series[key];
  const ctx = document.getElementById("mainChart").getContext("2d");
  if (mainChart) {{ mainChart.destroy(); mainChart = null; }}

  const base = {{
    label: cfg.label, data: s.values,
    borderColor: cfg.color, backgroundColor: cfg.fill,
    borderWidth: 2, pointRadius: 0, pointHoverRadius: 4,
    fill: cfg.type !== "bar", tension: cfg.tension,
  }};
  const datasets = [base];

  if (key === "price") {{
    const r  = calc(getVal("adt"), getVal("hibor"), getVal("ipo"), getVal("pe"));
    const n  = s.dates.length;
    const fl = (v) => Array(n).fill(v);
    datasets.push({{ label:"Bear P/E ({pe_low:.0f}x)",     data:fl(r.priceLow),    borderColor:"rgba(211,47,47,0.55)",  borderDash:[5,3], borderWidth:1.5, pointRadius:0, fill:false, tension:0 }});
    datasets.push({{ label:"Fair P/E (model)",             data:fl(r.priceFair),   borderColor:"#1A2E4A",               borderDash:[7,3], borderWidth:2,   pointRadius:0, fill:false, tension:0 }});
    datasets.push({{ label:"Bull P/E ({pe_high:.0f}x)",    data:fl(r.priceHigh),   borderColor:"rgba(46,125,50,0.55)",  borderDash:[5,3], borderWidth:1.5, pointRadius:0, fill:false, tension:0 }});
    datasets.push({{ label:"Analyst HKD {tgt:.0f}",        data:fl(ANALYST_TARGET),borderColor:"#f39c12",               borderDash:[9,4], borderWidth:1.5, pointRadius:0, fill:false, tension:0 }});
  }}
  if (key === "pe") {{
    const n = s.dates.length;
    datasets.push({{ label:"Bear {pe_low:.0f}x", data:Array(n).fill(PE_LOW),  borderColor:"rgba(211,47,47,0.5)", borderDash:[5,3], borderWidth:1.5, pointRadius:0, fill:false, tension:0 }});
    datasets.push({{ label:"Bull {pe_high:.0f}x",data:Array(n).fill(PE_HIGH), borderColor:"rgba(46,125,50,0.5)", borderDash:[5,3], borderWidth:1.5, pointRadius:0, fill:false, tension:0 }});
  }}
  if (key === "adt") {{
    base.backgroundColor = s.dates.map(yr => yr === "2026" ? "rgba(25,118,210,0.3)" : "rgba(25,118,210,0.8)");
    base.borderColor     = s.dates.map(yr => yr === "2026" ? "#1976D2" : "transparent");
    base.borderWidth     = 2;
  }}
  if (key === "hibor") {{
    const n = s.dates.length;
    datasets.push({{ label:"Your Forecast", data:Array(n).fill(getVal("hibor")), borderColor:"#1A2E4A", borderDash:[6,3], borderWidth:2, pointRadius:0, fill:false, tension:0 }});
  }}

  mainChart = new Chart(ctx, {{
    type: cfg.type === "bar" ? "bar" : "line",
    data: {{ labels: s.dates, datasets }},
    options: {{
      responsive:true, maintainAspectRatio:true, aspectRatio:3, animation:{{duration:250}},
      interaction:{{ mode:"index", intersect:false }},
      plugins:{{
        legend:{{ display:true, position:"top", labels:{{ boxWidth:12, font:{{size:11}} }} }},
        tooltip:{{ callbacks:{{ label:(c) => ` ${{c.dataset.label}}: ${{c.parsed.y != null ? c.parsed.y.toLocaleString("en-HK",{{minimumFractionDigits:1,maximumFractionDigits:1}}) : "N/A"}}` }} }},
      }},
      scales:{{
        x:{{
          type:"category",
          ticks:{{ maxTicksLimit: key==="adt"?30:12, maxRotation: key==="adt"?45:0, font:{{size:10}},
                   callback:function(v,i) {{ const l=this.getLabelForValue(v); return l?l.substring(0,7):""; }} }},
          grid:{{ display:false }},
        }},
        y:{{
          title:{{ display:true, text:cfg.yLabel, font:{{size:10}} }},
          ticks:{{ font:{{size:10}}, callback:(v)=>v.toLocaleString() }},
          grid:{{ color:"rgba(0,0,0,0.04)" }},
        }},
      }},
    }},
  }});
  document.getElementById("chart-desc").textContent = cfg.desc;
}}

function updatePriceBands(r) {{
  if (!mainChart || currentChart !== "price") return;
  const n = mainChart.data.labels.length;
  if (mainChart.data.datasets.length >= 5) {{
    mainChart.data.datasets[1].data = Array(n).fill(r.priceLow);
    mainChart.data.datasets[2].data = Array(n).fill(r.priceFair);
    mainChart.data.datasets[3].data = Array(n).fill(r.priceHigh);
    mainChart.update("none");
  }}
}}

function showChart(key, el) {{
  currentChart = key;
  document.querySelectorAll(".chart-tab").forEach(b => b.classList.remove("active"));
  const t = document.getElementById("tab-" + key);
  if (t) t.classList.add("active");
  buildChart(key);
}}

update();
showChart("price");
</script>
</body>
</html>"""

out_path = os.path.join(BASE, "dashboard_0388.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(HTML)

size_kb = os.path.getsize(out_path) // 1024
print(f"Generated: {out_path}  ({size_kb} KB)")
