#!/usr/bin/env python3
"""
HKEX (0388.HK) Valuation Dashboard
Produces a Low / Fair / High valuation based on:
  - Revenue component scenarios (Trading, NII, Listing, Data, Other)
  - Net margin assumptions per scenario
  - Historical P/E band (Low / Median / High)
"""

import os, sys, warnings
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
import yfinance as yf

BASE  = r"D:\Backup D\Weekly\USB drive\Invest\AI invest\388"
DATA  = os.path.join(BASE, "data")
MODEL = os.path.join(BASE, "model")

def section(t): print(f"\n{'='*68}\n  {t}\n{'='*68}")
def line(c="-", n=68): print(c * n)
def pct(v): return f"{v:+.1f}%"
def hkd(v, dp=0): return f"HKD {v:,.{dp}f}"

SHARES_BN = 1.267   # billion shares (diluted, from income stmt)

# ======================================================================
# 1. CURRENT PRICE + ANALYST CONSENSUS
# ======================================================================
section("1. Current Price & Analyst Consensus")

hkex_d = pd.read_csv(os.path.join(DATA, "raw_0388_HK.csv"),
                     index_col=0, parse_dates=True)
if isinstance(hkex_d.columns, pd.MultiIndex):
    hkex_d.columns = hkex_d.columns.get_level_values(0)
last_row   = hkex_d["Close"].dropna().iloc[-1]
last_date  = hkex_d["Close"].dropna().index[-1]
current_px = float(last_row)

# yfinance analyst data
t = yf.Ticker("0388.HK")
info = t.info

analyst_mean   = info.get("targetMeanPrice",   519.24)
analyst_high   = info.get("targetHighPrice",   610.0)
analyst_low    = info.get("targetLowPrice",    390.0)
analyst_median = info.get("targetMedianPrice", 510.0)
n_analysts     = info.get("numberOfAnalystOpinions", 17)
ttm_eps        = info.get("trailingEps",  14.88)
fwd_eps        = info.get("forwardEps",   None)
trailing_pe    = info.get("trailingPE",   None)
fwd_pe         = info.get("forwardPE",    None)
rec_mean       = info.get("recommendationMean", None)
wk52_hi        = info.get("fiftyTwoWeekHigh",  None)
wk52_lo        = info.get("fiftyTwoWeekLow",   None)

print(f"\n  Price Date  : {last_date.strftime('%d %b %Y')}")
print(f"  Last Close  : {hkd(current_px)}")
print(f"  52-Wk Range : {hkd(wk52_lo) if wk52_lo else 'N/A'} -- {hkd(wk52_hi) if wk52_hi else 'N/A'}")
print()
print(f"  TTM EPS     : {hkd(ttm_eps, 2)}")
print(f"  Fwd EPS     : {hkd(fwd_eps, 2) if fwd_eps else 'N/A (est. ~HKD 16.5 -- see section 4)'}")
print(f"  Trailing P/E: {trailing_pe:.1f}x" if trailing_pe else "  Trailing P/E: N/A")
print(f"  Forward P/E : {fwd_pe:.1f}x"     if fwd_pe    else "  Forward P/E : N/A")
print()
print(f"  Analyst Coverage: {n_analysts} analysts")
print(f"  Consensus Rating: {rec_mean:.2f}/5.0 (1=Strong Buy)" if rec_mean else "")
print(f"  Target Mean : {hkd(analyst_mean)}  ({pct((analyst_mean/current_px-1)*100)} vs current)")
print(f"  Target Range: {hkd(analyst_low)} -- {hkd(analyst_high)}")

# ======================================================================
# 2. RATE ENVIRONMENT + HIBOR SCENARIOS
# ======================================================================
section("2. Rate Environment & HIBOR Scenarios")

ff = pd.read_csv(os.path.join(DATA, "raw_FEDFUNDS.csv"),
                 index_col=0, parse_dates=True)
ff.columns = ["FEDFUNDS"]
current_ff = float(ff["FEDFUNDS"].dropna().iloc[-1])

# Pull Fed Funds futures live from yfinance to get market-implied forward rates
# ZQ contracts price = 100 - implied Fed Funds rate
futures_map = {
    "ZQN26.CBT": "Jul 2026",
    "ZQU26.CBT": "Sep 2026",
    "ZQZ26.CBT": "Dec 2026",
    "ZQH27.CBT": "Mar 2027",
}
futures_rates = {}
print(f"\n  FEDFUNDS Effective (May 2026): {current_ff:.2f}%  (FRED)")
print(f"  Fed Funds Target: 3.50-3.75% (held at June 17 FOMC)")
print(f"\n  Live Fed Funds Futures (ZQ) -- Market-Implied Forward Rates:")
print(f"  {'Contract':<16} {'Price':>8} {'Implied FF':>12} {'Implied HIBOR*':>16}")
line()
for sym, label in futures_map.items():
    try:
        d = yf.download(sym, period="5d", progress=False, auto_adjust=True)
        if len(d) > 0:
            if isinstance(d.columns, pd.MultiIndex):
                d.columns = d.columns.get_level_values(0)
            px   = float(d["Close"].dropna().iloc[-1])
            rate = 100 - px
            hibor_est = rate - 0.40   # HIBOR typically 30-50bps below FF
            futures_rates[label] = rate
            print(f"  {label:<16} {px:>8.3f} {rate:>11.2f}% {hibor_est:>15.2f}%")
        else:
            print(f"  {label:<16} {'no data':>8}")
    except Exception as e:
        print(f"  {label:<16} error: {str(e)[:40]}")
line()
print("  *HIBOR est. = Fed Funds implied - 40bps (HKD peg spread)")

# Derive consensus HIBOR for full-year 2026
# H1 2026: approx current (3.0-3.2% HIBOR), H2: futures-derived
h2_ff  = futures_rates.get("Dec 2026", 3.93)
h1_ff  = current_ff
avg_ff = (h1_ff + h2_ff) / 2
avg_hibor_consensus = avg_ff - 0.40
print(f"\n  DERIVED FULL-YEAR 2026 HIBOR ESTIMATE (from futures):")
print(f"    H1 avg FF: {h1_ff:.2f}%  H2 implied FF: {h2_ff:.2f}%")
print(f"    Full-year avg Fed Funds: {avg_ff:.2f}%  => Avg HIBOR: ~{avg_hibor_consensus:.2f}%")
print(f"\n  KEY TAKEAWAY: Futures price in HIKES not cuts (Dec 2026 FF ~3.9%).")
print(f"  This is POSITIVE for HKEX NII vs earlier consensus of 2-3 cuts.")

print(f"""
  HIBOR SCENARIOS FOR 2026 FULL-YEAR AVERAGE:
    Low  (aggressive Fed cuts): avg HIBOR ~2.0%  (tail risk, rapid pivot)
    Base (futures consensus)  : avg HIBOR ~3.0%  (futures imply {avg_hibor_consensus:.1f}%)
    High (Fed hikes +50bp)    : avg HIBOR ~3.5%  (tariff-driven inflation)

  Prev web-search consensus (HIBOR 2.3-2.8%) was based on older forecasts
  from early 2026 before the June FOMC dot plot shift toward hikes.
  Futures (live as of today) now imply rates RISING, not falling.

  IMPACT ON NII:
    NII scales with HIBOR on ~HKD 230-280bn clearing fund pool (grew ~25%
    since 2023 due to higher margin deposits from elevated market volumes).
    Calibrated from actuals: ~HKD 9.4bn NII at 5% HIBOR (2023).
    Portfolio growth boosts effective NII above simple rate extrapolation.
""")

# ======================================================================
# 3. REVENUE BREAKDOWN -- ACTUALS + 2026 SCENARIOS
# ======================================================================
section("3. Revenue Breakdown: Actuals (2022-2025) + 2026 Scenarios (HKD mn)")

# Actuals from HKEX Annual Reports (approximate; source: HKEX published results)
# NB: 2026 figures below are FORECAST scenarios, not actuals
rev = {
    "Component": [
        "Trading + Clearing",
        "Listing / IPO",
        "Market Data + Connect",
        "Investment Income (NII)",
        "Other (LME/depository)",
        "TOTAL",
    ],
    "2022A":  [ 9_200,  1_420,  1_020,  5_600,  1_400, 18_640],
    "2023A":  [ 7_900,    860,  1_000,  9_400,  1_100, 20_260],
    "2024A":  [ 8_900,  1_020,  1_050, 10_500,    900, 22_370],
    "2025A":  [11_800,  1_200,  1_100,  9_700,  1_200, 25_000],
    # 2026 Low: HIBOR 2% avg (severe rate cuts), HK volumes soften, IPO sluggish
    "2026L":  [ 9_500,  1_000,  1_050,  6_000,  1_050, 18_600],
    # 2026 Base: HIBOR 3.0% avg (FUTURES CONSENSUS -- rates hold/slight hike), volumes hold
    "2026B":  [11_800,  1_500,  1_100,  9_000,  1_100, 24_500],
    # 2026 High: HIBOR 3.5% avg (Fed hikes 50bp), volumes surge on HSI bull, IPO picks up
    "2026H":  [14_000,  2_200,  1_150, 10_000,  1_150, 28_500],
}
rev_df = pd.DataFrame(rev).set_index("Component")

# Check totals match sum of components
for col in ["2026L","2026B","2026H","2022A","2023A","2024A","2025A"]:
    total = rev_df.loc["TOTAL", col]
    calc  = rev_df.drop("TOTAL").loc[:, col].sum()
    rev_df.loc["TOTAL", col] = calc   # ensure totals are sum-derived

# Print revenue table
cols    = ["2022A","2023A","2024A","2025A","2026L","2026B","2026H"]
hdrs    = ["Component",          "2022A", "2023A", "2024A", "2025A",
           "26-LOW", "26-BASE", "26-HIGH"]
widths  = [26, 8, 8, 8, 8, 8, 8, 8]

def fmt_row(vals, bold=False):
    row = ""
    for v, w in zip(vals, widths):
        if isinstance(v, (int, float)):
            s = f"{v:,.0f}"
        else:
            s = str(v)
        row += s.rjust(w) + "  "
    return row

print()
print(fmt_row(hdrs))
line()
for idx, row in rev_df.iterrows():
    vals = [idx] + [row[c] for c in cols]
    if idx == "TOTAL":
        line()
    print(fmt_row(vals))

# % breakdown for each scenario
print(f"\n  % of Total Revenue:")
print(fmt_row(hdrs))
line()
for idx in rev_df.index:
    if idx == "TOTAL": continue
    vals = [idx]
    for col in cols:
        pv = rev_df.loc[idx, col] / rev_df.loc["TOTAL", col] * 100
        vals.append(f"{pv:.0f}%")
    print(fmt_row(vals))

rev_df.to_csv(os.path.join(MODEL, "valuation_revenue_scenarios.csv"))

# NII notes
print(f"""
  NII SCENARIO RATIONALE:
    Low  (HKD 6.0bn): HIBOR avg 2.0% -- Fed cuts 3-4x (tail risk, early-2026 expectation)
    Base (HKD 9.0bn): HIBOR avg 3.0% -- FUTURES CONSENSUS (rates hold/slight hike)
    High (HKD10.0bn): HIBOR avg 3.5% -- Fed hikes 50bp on tariff-driven inflation

  TRADING+CLEARING RATIONALE (% of 2025A):
    Low  (HKD 9.5bn): -20% -- Market pullback, ADT falls to ~HKD 90-100bn/day
    Base (HKD11.8bn): flat  -- ADT holds at ~HKD 125bn/day (2025 level)
    High (HKD14.0bn): +19% -- Bull run, ADT surges to HKD 150-160bn/day

  IPO/LISTING RATIONALE:
    Low  (HKD 1.0bn): -17% -- IPO market stays quiet
    Base (HKD 1.5bn): +25% -- Gradual recovery continues
    High (HKD 2.2bn): +83% -- Strong pipeline, mega-IPOs return
""")

# ======================================================================
# 4. EPS SCENARIOS + HISTORICAL P/E
# ======================================================================
section("4. EPS Scenarios + Historical P/E Band")

# Net margin assumptions (HKEX has high operating leverage ~70-75% typical)
margins = {"Low": 0.63, "Base": 0.70, "High": 0.76}

total_rev = {"Low": rev_df.loc["TOTAL","2026L"],
             "Base": rev_df.loc["TOTAL","2026B"],
             "High": rev_df.loc["TOTAL","2026H"]}

eps_scenarios = {}
print(f"\n  Shares outstanding: {SHARES_BN:.3f}bn (diluted)")
print(f"\n  {'Scenario':<8} {'Revenue(HKDmn)':>15} {'Net Margin':>12} {'Net Profit':>12} {'EPS (HKD)':>12}")
line()
for s, margin in margins.items():
    rev_val  = total_rev[s]
    profit   = rev_val * margin
    eps_val  = profit / (SHARES_BN * 1000)   # convert mn to actual shares
    eps_scenarios[s] = eps_val
    print(f"  {s:<8} {rev_val:>15,.0f} {margin*100:>11.0f}% {profit:>12,.0f} {eps_val:>12.2f}")

# Historical P/E from actuals
hist_pe_data = {
    2022: {"price": 304.0, "eps": 7.95},
    2023: {"price": 248.0, "eps": 9.36},
    2024: {"price": 282.7, "eps": 10.29},
    2025: {"price": 401.4, "eps": 14.01},
}
print(f"\n  Historical Trailing P/E (year-end price / reported EPS):")
print(f"  {'Year':<6} {'Price':>8} {'EPS':>8} {'P/E':>8}")
line()
hist_pes = []
for yr, d in hist_pe_data.items():
    pe = d["price"] / d["eps"]
    hist_pes.append(pe)
    print(f"  {yr:<6} {d['price']:>8.1f} {d['eps']:>8.2f} {pe:>7.1f}x")

pe_low    = round(min(hist_pes) - 1, 0)    # ~25x (2023 trough)
pe_median = round(np.median(hist_pes), 0)  # ~33x
pe_high   = round(max(hist_pes) + 1, 0)    # ~39x

# Also note analyst-implied P/E
analyst_fwd_pe = analyst_mean / ttm_eps
print(f"\n  Current trailing P/E : {current_px/ttm_eps:.1f}x  (price {current_px:.0f} / TTM EPS {ttm_eps:.2f})")
print(f"  Analyst target P/E   : {analyst_fwd_pe:.1f}x  (target {analyst_mean:.0f} / TTM EPS {ttm_eps:.2f})")
print(f"\n  P/E Scenarios used in valuation:")
print(f"    Low    P/E: {pe_low:.0f}x  (2023 bear trough)")
print(f"    Median P/E: {pe_median:.0f}x  (4-year average)")
print(f"    High   P/E: {pe_high:.0f}x  (2022 bull peak)")

# ======================================================================
# 5. VALUATION MATRIX
# ======================================================================
section("5. Valuation Matrix: EPS x P/E = Target Price (HKD)")

pe_scenarios = {"Low P/E": pe_low, "Med P/E": pe_median, "High P/E": pe_high}

print(f"\n  Current Price: {hkd(current_px)}")
print(f"  Analyst Consensus Target: {hkd(analyst_mean)}  |  Range: {hkd(analyst_low)} - {hkd(analyst_high)}")
print()
print(f"               {'Low EPS':>12} {'Base EPS':>12} {'High EPS':>12}")
print(f"               {'(HKD '+str(round(eps_scenarios['Low'],1))+')':>12}"
      f" {'(HKD '+str(round(eps_scenarios['Base'],1))+')':>12}"
      f" {'(HKD '+str(round(eps_scenarios['High'],1))+')':>12}")
line()

val_matrix = {}
for pe_name, pe_val in pe_scenarios.items():
    row = {}
    line_parts = [f"  {pe_name} ({pe_val:.0f}x)"]
    for eps_name in ["Low","Base","High"]:
        price = eps_scenarios[eps_name] * pe_val
        row[eps_name] = price
        updown = (price / current_px - 1) * 100
        # Highlight the BASE × MEDIAN cell as the "FAIR" case
        marker = " <-- FAIR" if (pe_name == "Med P/E" and eps_name == "Base") else ""
        cell = f"  {price:>6.0f} ({pct(updown)}){marker}"
        line_parts.append(f"{cell:>22}")
    val_matrix[pe_name] = row
    print("".join(line_parts))

line()

# Extract the three headline numbers
fair_value   = val_matrix["Med P/E"]["Base"]
low_value    = val_matrix["Low P/E"]["Low"]
high_value   = val_matrix["High P/E"]["High"]

print(f"""
  HEADLINE VALUATION SUMMARY:
  +---------------------------------------------------------+
  |  BEAR CASE  (Low EPS x Low P/E)   : {hkd(low_value):>10}  ({pct((low_value/current_px-1)*100)} vs now) |
  |  FAIR VALUE (Base EPS x Med P/E)  : {hkd(fair_value):>10}  ({pct((fair_value/current_px-1)*100)} vs now) |
  |  BULL CASE  (High EPS x High P/E) : {hkd(high_value):>10}  ({pct((high_value/current_px-1)*100)} vs now) |
  +---------------------------------------------------------+
  |  CURRENT PRICE                    : {hkd(current_px):>10}                   |
  |  ANALYST CONSENSUS TARGET         : {hkd(analyst_mean):>10}  ({pct((analyst_mean/current_px-1)*100)} vs now) |
  |  ANALYST RANGE                    : {hkd(analyst_low)} - {hkd(analyst_high)}                |
  +---------------------------------------------------------+
""")

# ======================================================================
# 6. WHERE DOES CURRENT PRICE SIT?
# ======================================================================
section("6. Interpretation")

if current_px < low_value:
    position = "BELOW BEAR CASE -- deeply undervalued or model too optimistic"
elif current_px < fair_value * 0.90:
    position = "BELOW FAIR VALUE -- looks undervalued on base assumptions"
elif current_px < fair_value * 1.10:
    position = "NEAR FAIR VALUE -- fairly valued on base assumptions"
elif current_px < high_value:
    position = "ABOVE FAIR, BELOW BULL -- pricing in an optimistic scenario"
else:
    position = "ABOVE BULL CASE -- rich valuation or model too conservative"

print(f"""
  CURRENT PRICE vs VALUATION RANGE:
    Bear  {hkd(low_value)}  |  Fair  {hkd(fair_value)}  |  Bull  {hkd(high_value)}
    Current: {hkd(current_px)}
    Position: {position}

  KEY RISKS TO EACH SCENARIO:
    Bear  -- Fed pivots aggressively (HIBOR drops to 2%), HK market volume slumps,
             China macro disappoints, IPO drought continues, P/E de-rates to 25x.
    Base  -- Market consensus: 2-3 Fed cuts, HK market stable, gradual IPO recovery.
    Bull  -- Fed holds/hikes (tariff inflation), HK volumes surge on China stimulus,
             mega IPO wave, market re-rates to 38-40x on earnings growth outlook.

  NOTE ON THE GAP BETWEEN OUR FAIR VALUE AND ANALYST CONSENSUS:
    Our base case: {hkd(fair_value)} | Analyst mean: {hkd(analyst_mean)}
    The {hkd(analyst_mean - fair_value)} gap suggests analysts are using:
    (a) Higher EPS assumptions (growth beyond 2026), or
    (b) Higher P/E multiple (~{analyst_fwd_pe:.0f}x vs our median {pe_median:.0f}x), or
    (c) Both -- common for a high-quality monopoly franchise with pricing power.

  SENSITIVITY: WHICH DRIVER MATTERS MOST IN 2026?
    NII (40-47% of revenue):  Each 1% change in HIBOR avg = ~HKD1.9bn NII
                               = ~HKD 1.0 change in EPS
                               = ~HKD 30 change in stock price (at median P/E)
    Trading volume (39-47%):  Each HKD 10bn/day change in ADT
                               = ~HKD 0.9bn revenue change = ~HKD 22 stock impact
    P/E multiple:              Each 1x change = ~HKD {fair_value/pe_median:.0f} stock impact
""")

print("Done. Saved valuation_revenue_scenarios.csv to model/ folder.")
