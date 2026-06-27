#!/usr/bin/env python3
"""
388.HK Lead-Lag Analysis
Focus: HK Market Turnover and IPO Amount vs 0388.HK price
- Cross-correlation at lags -6 to +6 months
- Bidirectional Granger causality
- Monthly OLS scanning all lag structures
- Weekly OLS for comparison
"""

import os, sys, warnings, io
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
import requests
import yfinance as yf
import statsmodels.api as sm
from statsmodels.tsa.stattools import grangercausalitytests, ccf as sm_ccf

BASE  = r"D:\Backup D\Weekly\USB drive\Invest\AI invest\388"
DATA  = os.path.join(BASE, "data")
MODEL = os.path.join(BASE, "model")

def section(t):
    print(f"\n{'='*70}\n  {t}\n{'='*70}")

# ======================================================================
# 1. LOAD 0388.HK AND HSI (ALREADY DOWNLOADED)
# ======================================================================
section("1. Loading 0388.HK and HSI data")

hkex_d = pd.read_csv(os.path.join(DATA, "raw_0388_HK.csv"),
                     index_col=0, parse_dates=True)
hsi_d  = pd.read_csv(os.path.join(DATA, "raw_HSI.csv"),
                     index_col=0, parse_dates=True)

# Flatten multi-level cols if present
for df in [hkex_d, hsi_d]:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

print(f"  0388.HK: {len(hkex_d)} days [{hkex_d.index[0].date()} - {hkex_d.index[-1].date()}]")
print(f"  ^HSI   : {len(hsi_d)}  days [{hsi_d.index[0].date()}  - {hsi_d.index[-1].date()}]")

# ======================================================================
# 2. BUILD TURNOVER PROXY: HSI Volume x HSI Level (HKD-weighted activity)
#    More meaningful than raw share count because price differences are huge
# ======================================================================
section("2. HK Market Turnover Proxy")

# Daily HKD-equivalent activity index
hsi_d["Turnover_idx"] = hsi_d["Volume"] * hsi_d["Close"]
hsi_d["Turnover_idx"] = hsi_d["Turnover_idx"].replace(0, np.nan)

print("  Using: ^HSI Volume x HSI Level as turnover proxy")
print("  Note: actual HKD turnover (HKEX monthly stats) would be ideal but")
print("        requires manual download from hkex.com.hk/Market-Data/Statistics")
print(f"  Daily rows with valid turnover: {hsi_d['Turnover_idx'].notna().sum()}")

# ======================================================================
# 3. ATTEMPT TO FETCH HKEX MONTHLY TURNOVER AND IPO DATA
#    HKEX publishes an Excel file at a known URL pattern
# ======================================================================
section("3. Attempting HKEX Monthly Statistics download")

def try_hkex_stats():
    """
    HKEX publishes monthly market statistics Excel.
    Returns DataFrame with columns [Month, ADT_HKDbn, IPO_Amount_HKDbn, IPO_Count]
    or None if download fails.
    """
    # Try the HKEX Fact Sheet / statistics page
    # Pattern: https://www.hkex.com.hk/-/media/HKEX-Market/Market-Data/Statistics/
    # Consolidated-Reports/Securities-Statistics/Fact-Sheet/YYYY/factsheet_YYYY_MM.xlsx
    # The naming is inconsistent; we try the known working endpoint via Stooq proxy
    # or direct HKEX stats CSV.

    # HKEX publishes a comprehensive fact sheet. Try the annual one first.
    url = ("https://www.hkex.com.hk/-/media/HKEX-Market/Market-Data/Statistics/"
           "Consolidated-Reports/Securities-Statistics/Fact-Sheet/2025/factsheet_2025_12.xlsx")
    try:
        r = requests.get(url, timeout=20,
                         headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            return pd.read_excel(io.BytesIO(r.content), sheet_name=0)
    except Exception:
        pass
    return None

hkex_stats = try_hkex_stats()
if hkex_stats is not None:
    print("  HKEX monthly stats: downloaded successfully")
    print(hkex_stats.head())
else:
    print("  HKEX monthly stats: not available via automated URL")
    print("  -> Proceeding with HSI-based proxy for turnover")
    print("  -> IPO data: manual entry required (see instructions at end)")

# ======================================================================
# 4. BUILD MONTHLY PANEL
# ======================================================================
section("4. Building monthly panel (resampled to month-end)")

# Monthly: last trading day of each month
def monthly_last(df, col):
    return df[[col]].resample("ME").last().dropna()

def monthly_sum(df, col):
    return df[[col]].resample("ME").sum()

def monthly_mean(df, col):
    return df[[col]].resample("ME").mean()

# 0388.HK monthly close and log return
hkex_m = monthly_last(hkex_d, "Close")
hkex_m.columns = ["HKEX_close"]
hkex_m["D_ln_0388"] = np.log(hkex_m["HKEX_close"] / hkex_m["HKEX_close"].shift(1))

# HK Turnover proxy: monthly total (sum of daily)
turn_m = monthly_sum(hsi_d, "Turnover_idx")
turn_m.columns = ["Turnover"]
turn_m["D_ln_Turn"] = np.log(turn_m["Turnover"] / turn_m["Turnover"].shift(1))

# HSI return (for control)
hsi_m = monthly_last(hsi_d, "Close")
hsi_m.columns = ["HSI"]
hsi_m["D_ln_HSI"] = np.log(hsi_m["HSI"] / hsi_m["HSI"].shift(1))

# Merge
panel_m = (
    hkex_m[["D_ln_0388", "HKEX_close"]]
    .join(turn_m[["D_ln_Turn", "Turnover"]], how="inner")
    .join(hsi_m[["D_ln_HSI"]],              how="inner")
).dropna(subset=["D_ln_0388", "D_ln_Turn"])

panel_m.to_csv(os.path.join(DATA, "panel_monthly.csv"))
print(f"  Monthly panel: {len(panel_m)} months  "
      f"[{panel_m.index[0].strftime('%Y-%m')} - {panel_m.index[-1].strftime('%Y-%m')}]")
print(f"  Columns: {list(panel_m.columns)}")
print(f"\n  Note on monthly sample size:")
print(f"  {len(panel_m)} months / ~10 per parameter = can support ~{len(panel_m)//10} parameters comfortably")

# Also build weekly panel
hkex_w   = hkex_d.resample("W-FRI").last()[["Close"]].rename(columns={"Close":"HKEX_close"})
hkex_w["D_ln_0388"] = np.log(hkex_w["HKEX_close"] / hkex_w["HKEX_close"].shift(1))
turn_w   = hsi_d.resample("W-FRI").sum()[["Turnover_idx"]].rename(columns={"Turnover_idx":"Turnover"})
turn_w["D_ln_Turn"] = np.log(turn_w["Turnover"] / turn_w["Turnover"].shift(1))
hsi_w    = hsi_d.resample("W-FRI").last()[["Close"]].rename(columns={"Close":"HSI"})
hsi_w["D_ln_HSI"] = np.log(hsi_w["HSI"] / hsi_w["HSI"].shift(1))

panel_w = (
    hkex_w[["D_ln_0388"]]
    .join(turn_w[["D_ln_Turn"]], how="inner")
    .join(hsi_w[["D_ln_HSI"]],  how="inner")
).dropna()
panel_w.to_csv(os.path.join(DATA, "panel_weekly.csv"))
print(f"\n  Weekly panel : {len(panel_w)} weeks   "
      f"[{panel_w.index[0].strftime('%Y-%m-%d')} - {panel_w.index[-1].strftime('%Y-%m-%d')}]")

# ======================================================================
# 5. CROSS-CORRELATION FUNCTION (CCF)
#    Convention used here:
#      ccf_table[k] = corr( feature[t], 0388_return[t + k] )
#      k > 0 => feature at t correlates with 0388 k months LATER => Feature LEADS 0388
#      k < 0 => 0388 at t-|k| correlates with feature at t => 0388 LEADS feature
# ======================================================================
section("5. Cross-Correlation Function (CCF) -- monthly")

MAX_LAG_CCF = 6   # months

def compute_ccf(x, y, max_lag):
    """
    Returns DataFrame: lag k, CCF value, interpretation.
    corr(x[t], y[t+k])
      k > 0: x leads y by k periods
      k < 0: y leads x by |k| periods (or equivalently, x lags y)
      k = 0: contemporaneous
    """
    x = x.dropna()
    y = y.dropna()
    idx = x.index.intersection(y.index)
    x, y = x[idx], y[idx]

    rows = []
    for k in range(-max_lag, max_lag + 1):
        if k >= 0:
            x_aligned = x.iloc[:len(x)-k]   if k > 0 else x
            y_aligned = y.iloc[k:]           if k > 0 else y
        else:
            x_aligned = x.iloc[-k:]
            y_aligned = y.iloc[:len(y)+k]

        n = min(len(x_aligned), len(y_aligned))
        if n < 10:
            rows.append({"lag_k": k, "CCF": np.nan, "Direction": ""})
            continue
        c = np.corrcoef(x_aligned.values[:n], y_aligned.values[:n])[0, 1]

        if k > 0:
            direction = f"Feature leads 0388 by {k}m"
        elif k < 0:
            direction = f"0388 leads Feature by {-k}m"
        else:
            direction = "Contemporaneous"
        rows.append({"lag_k": k, "CCF": round(c, 4), "Direction": direction})
    return pd.DataFrame(rows)

# CCF for Turnover
print("\n  CCF: D_ln_Turn (HK market turnover change) vs D_ln_0388")
print("  Positive CCF = same-direction relationship")
print("  k>0 means turnover change today predicts 0388 return k months later")
print()
ccf_turn = compute_ccf(panel_m["D_ln_Turn"], panel_m["D_ln_0388"], MAX_LAG_CCF)
print(ccf_turn.to_string(index=False))
ccf_turn.to_csv(os.path.join(MODEL, "ccf_turnover_monthly.csv"), index=False)

# Find peak lag
peak = ccf_turn.loc[ccf_turn["CCF"].abs().idxmax()]
print(f"\n  Peak CCF = {peak['CCF']:.4f} at lag k={int(peak['lag_k'])}  ({peak['Direction']})")

# ======================================================================
# 6. BIDIRECTIONAL GRANGER CAUSALITY -- MONTHLY
# ======================================================================
section("6. Bidirectional Granger Causality -- monthly (max lag = 6m)")

MAX_LAG_GC = 6

def granger_table(x_name, x_s, y_name, y_s, max_lag):
    """Tests x -> y and y -> x at lags 1..max_lag"""
    combo = pd.concat([x_s, y_s], axis=1).dropna()
    combo.columns = [x_name, y_name]

    rows = []
    for direction, df_cols in [(f"{x_name} -> {y_name}", [y_name, x_name]),
                                (f"{y_name} -> {x_name}", [x_name, y_name])]:
        gc = grangercausalitytests(combo[df_cols], maxlag=max_lag, verbose=False)
        pvals = [gc[lag][0]["ssr_ftest"][1] for lag in range(1, max_lag + 1)]
        minp  = min(pvals)
        best_lag = pvals.index(minp) + 1
        pstr  = "  ".join([f"L{i+1}:{p:.3f}" for i, p in enumerate(pvals)])
        rows.append({
            "Direction"   : direction,
            "p (L1-L6)"  : pstr,
            "Min p"      : round(minp, 4),
            "Best lag"   : best_lag,
            "Conclusion" : "YES ***" if minp < 0.01
                      else "YES **"  if minp < 0.05
                      else "YES *"   if minp < 0.10
                      else "NO"
        })
    return pd.DataFrame(rows)

gc_df = granger_table("D_ln_Turn", panel_m["D_ln_Turn"],
                       "D_ln_0388", panel_m["D_ln_0388"], MAX_LAG_GC)
print("\n  Turnover <-> 0388:")
print(gc_df.to_string(index=False))
gc_df.to_csv(os.path.join(MODEL, "granger_bidir_monthly.csv"), index=False)

# Also test weekly for comparison
gc_df_w = granger_table("D_ln_Turn", panel_w["D_ln_Turn"],
                         "D_ln_0388", panel_w["D_ln_0388"], 8)
print("\n  Turnover <-> 0388 (WEEKLY, max lag=8w):")
print(gc_df_w.to_string(index=False))
gc_df_w.to_csv(os.path.join(MODEL, "granger_bidir_weekly.csv"), index=False)

# ======================================================================
# 7. LAG-SCAN OLS -- MONTHLY
#    Try each lag k = -3..+3 months of turnover as the sole predictor
#    (negative k = 0388 leads turnover; positive k = turnover leads 0388)
#    We report R2 to identify which lag gives the best fit
# ======================================================================
section("7. Monthly OLS Lag Scan: which lag of Turnover best explains 0388?")

print("\n  Scanning lags k = -3 (0388 leads) to +6 (turnover leads 0388)")
print("  Model: D_ln_0388[t] = a + b * D_ln_Turn[t - k]")
print("  k > 0: turnover k months ago predicts 0388 return today")
print("  k < 0: 0388 return k months ago predicts turnover today (turnover lags)")
print()

scan_rows = []
for k in range(-3, 7):
    if k == 0:
        x = panel_m["D_ln_Turn"]
        y = panel_m["D_ln_0388"]
    elif k > 0:
        # Turnover lagged k months -> predict 0388 today
        x = panel_m["D_ln_Turn"].shift(k)
        y = panel_m["D_ln_0388"]
    else:
        # 0388 lagged |k| months -> predict turnover today (direction flipped)
        x = panel_m["D_ln_0388"].shift(-k)
        y = panel_m["D_ln_Turn"]

    combo = pd.concat([y, x], axis=1).dropna()
    combo.columns = ["Y", "X"]
    if len(combo) < 20:
        continue
    mdl = sm.OLS(combo["Y"], sm.add_constant(combo["X"])).fit(
              cov_type="HAC", cov_kwds={"maxlags": 3})

    if k == 0:
        label = "Contemporaneous"
    elif k > 0:
        label = f"Turn leads 0388 by {k}m"
    else:
        label = f"0388 leads Turn by {-k}m (direction reversed)"

    scan_rows.append({
        "k"      : k,
        "R2"     : round(mdl.rsquared, 4),
        "beta"   : round(mdl.params.iloc[1], 4),
        "p-val"  : round(mdl.pvalues.iloc[1], 4),
        "Sig"    : "***" if mdl.pvalues.iloc[1] < 0.01
              else "**"  if mdl.pvalues.iloc[1] < 0.05
              else "*"   if mdl.pvalues.iloc[1] < 0.10
              else "n.s.",
        "N"      : len(combo),
        "Label"  : label,
    })

scan_df = pd.DataFrame(scan_rows)
print(scan_df[["k","R2","beta","p-val","Sig","N","Label"]].to_string(index=False))
scan_df.to_csv(os.path.join(MODEL, "lag_scan_monthly.csv"), index=False)

best_k = scan_df.loc[scan_df["R2"].idxmax(), "k"]
best_r2 = scan_df["R2"].max()
print(f"\n  Best single-lag R2 = {best_r2:.4f} at k = {best_k}")

# ======================================================================
# 8. BEST-LAG OLS: MONTHLY + ERA SPLIT
# ======================================================================
section(f"8. Monthly OLS with optimal lag k={best_k} -- full + era split")

ERA_CUT = "2022-03-01"

def ols_monthly(df, lag_turn, label):
    d = df[["D_ln_0388", "D_ln_Turn", "D_ln_HSI"]].copy()
    d["Turn_lag"] = d["D_ln_Turn"].shift(lag_turn)
    sub = d[["D_ln_0388", "Turn_lag", "D_ln_HSI"]].dropna()
    if len(sub) < 12:
        print(f"\n  {label}: too few obs ({len(sub)}), skipped")
        return None
    Y = sub["D_ln_0388"]
    X = sm.add_constant(sub[["Turn_lag", "D_ln_HSI"]])
    mdl = sm.OLS(Y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
    print(f"\n  {label}  (N={len(sub)}, lag={lag_turn}m)")
    print(f"  R2={mdl.rsquared:.4f}  Adj-R2={mdl.rsquared_adj:.4f}  "
          f"RMSE={np.sqrt(mdl.mse_resid):.4f}")
    rows = []
    for v in mdl.params.index:
        rows.append({
            "Variable" : v,
            "beta"     : round(mdl.params[v],  4),
            "t-stat"   : round(mdl.tvalues[v], 3),
            "p-value"  : round(mdl.pvalues[v], 4),
            "Sig"      : "***" if mdl.pvalues[v] < 0.01
                    else "**"  if mdl.pvalues[v] < 0.05
                    else "*"   if mdl.pvalues[v] < 0.10
                    else "n.s."
        })
    print(pd.DataFrame(rows).to_string(index=False))
    return mdl

lag_use = int(best_k) if best_k >= 0 else 1   # use best positive lag (turnover leads 0388)
if lag_use < 1:
    lag_use = 1   # ensure at least 1-month lag for causal ordering

mdl_full = ols_monthly(panel_m, lag_use, "FULL PERIOD (2015-2026)")
mdl_e1   = ols_monthly(panel_m[panel_m.index < ERA_CUT],  lag_use, "ERA 1: Low-Rate (2015-Feb 2022)")
mdl_e2   = ols_monthly(panel_m[panel_m.index >= ERA_CUT], lag_use, "ERA 2: High-Rate (Mar 2022-2026)")

# ======================================================================
# 9. WEEKLY LAG SCAN FOR COMPARISON
# ======================================================================
section("9. Weekly Lag Scan (comparison: does weekly add info?)")

print("\n  Scanning weekly lags k = 0 to 8 weeks (turnover leading 0388)")
scan_w_rows = []
for k in range(0, 9):
    x = panel_w["D_ln_Turn"].shift(k)
    y = panel_w["D_ln_0388"]
    combo = pd.concat([y, x], axis=1).dropna()
    combo.columns = ["Y", "X"]
    if len(combo) < 30:
        continue
    mdl = sm.OLS(combo["Y"], sm.add_constant(combo["X"])).fit(
              cov_type="HAC", cov_kwds={"maxlags": 4})
    scan_w_rows.append({
        "lag (weeks)" : k,
        "R2"          : round(mdl.rsquared, 4),
        "beta"        : round(mdl.params.iloc[1], 4),
        "p-val"       : round(mdl.pvalues.iloc[1], 4),
        "Sig"         : "***" if mdl.pvalues.iloc[1] < 0.01
                   else "**"  if mdl.pvalues.iloc[1] < 0.05
                   else "*"   if mdl.pvalues.iloc[1] < 0.10
                   else "n.s.",
        "N"           : len(combo),
    })

scan_w_df = pd.DataFrame(scan_w_rows)
print(scan_w_df.to_string(index=False))
scan_w_df.to_csv(os.path.join(MODEL, "lag_scan_weekly.csv"), index=False)

# ======================================================================
# 10. IPO AMOUNT: INSTRUCTIONS + PLACEHOLDER STRUCTURE
# ======================================================================
section("10. IPO Amount: data source guide")

print("""
  IPO Amount is a key driver but requires manual data collection.
  Once collected, the same lead-lag analysis above applies.

  HOW TO GET THE DATA:
  --------------------
  1. HKEX Monthly Market Highlights (most reliable):
     URL: https://www.hkex.com.hk/Market-Data/Statistics/Consolidated-Reports/
          Securities-Statistics?sc_lang=en
     Download: "Monthly Market Highlights" Excel files
     Column needed: "Total Funds Raised - New listings (HKD bn)"
     Frequency: Monthly, goes back to ~2000

  2. Invest HK / KPMG annual reports have yearly IPO totals (less granular)

  3. Bloomberg terminal: HKEX IPO AMOUNT MONTHLY (if available)

  EXPECTED CSV FORMAT (save as data/ipo_monthly.csv):
  ---------------------------------------------------
  Date,IPO_Amount_HKDbn,IPO_Count
  2015-01-31,5.2,3
  2015-02-28,0.0,0
  ...

  ONCE COLLECTED: re-run this script. The lag scan below will auto-include it.
""")

ipo_path = os.path.join(DATA, "ipo_monthly.csv")
if os.path.exists(ipo_path):
    ipo_m = pd.read_csv(ipo_path, index_col=0, parse_dates=True)
    ipo_m.columns = [c.strip() for c in ipo_m.columns]
    print(f"  IPO data found: {len(ipo_m)} months")

    # Log-transform (add 1 to handle zero months)
    ipo_m["ln_IPO1"] = np.log(ipo_m["IPO_Amount_HKDbn"] + 1)
    ipo_m["D_ln_IPO1"] = ipo_m["ln_IPO1"].diff()

    # CCF for IPO
    section("  CCF: IPO Amount vs 0388.HK (monthly)")
    panel_ipo = panel_m.join(ipo_m[["D_ln_IPO1"]], how="inner").dropna()
    ccf_ipo = compute_ccf(panel_ipo["D_ln_IPO1"], panel_ipo["D_ln_0388"], MAX_LAG_CCF)
    print(ccf_ipo.to_string(index=False))
    ccf_ipo.to_csv(os.path.join(MODEL, "ccf_ipo_monthly.csv"), index=False)

    # Lag scan for IPO
    section("  Lag Scan: IPO Amount vs 0388.HK (monthly)")
    ipo_scan_rows = []
    for k in range(0, 7):
        x = panel_ipo["D_ln_IPO1"].shift(k)
        y = panel_ipo["D_ln_0388"]
        combo = pd.concat([y, x], axis=1).dropna()
        if len(combo) < 12:
            continue
        mdl_i = sm.OLS(combo.iloc[:,0], sm.add_constant(combo.iloc[:,1])).fit(
                    cov_type="HAC", cov_kwds={"maxlags":3})
        ipo_scan_rows.append({
            "lag(m)" : k,
            "R2"     : round(mdl_i.rsquared, 4),
            "beta"   : round(mdl_i.params.iloc[1], 4),
            "p-val"  : round(mdl_i.pvalues.iloc[1], 4),
            "Sig"    : "***" if mdl_i.pvalues.iloc[1] < 0.01 else
                       "**"  if mdl_i.pvalues.iloc[1] < 0.05 else
                       "*"   if mdl_i.pvalues.iloc[1] < 0.10 else "n.s.",
            "N"      : len(combo),
        })
    print(pd.DataFrame(ipo_scan_rows).to_string(index=False))
else:
    print(f"  [No ipo_monthly.csv found at {ipo_path}]")
    print("  Create the file per the instructions above and re-run.")

# ======================================================================
# 11. SUMMARY
# ======================================================================
section("11. Summary")

def r2s(m): return f"R2={m.rsquared:.4f}" if m else "N/A"

print(f"""
  TARGET: D_ln_0388 (monthly log-return of 0388.HK)
  KEY FEATURE: D_ln_Turn (monthly log-change in HK market turnover proxy)
  Lag used in OLS: {lag_use} month(s) (turnover leads 0388 by {lag_use}m)

  MONTHLY R2 RESULTS:
    Full period (2015-2026): {r2s(mdl_full)}
    Era 1 Low-Rate (15-22) : {r2s(mdl_e1)}
    Era 2 High-Rate (22-26): {r2s(mdl_e2)}

  INTERPRETATION:
    - Best CCF lag was {best_k} months (see ccf_turnover_monthly.csv)
    - Cross-correlations show when turnover leads vs lags 0388 price
    - Granger tests indicate causal direction (see granger_bidir_monthly.csv)
    - R2 is expected to improve significantly once real HKEX turnover
      (HKD billions from HKEX monthly stats) replaces the HSI volume proxy

  NEXT STEPS:
    1. Download actual HK market ADT from HKEX monthly stats Excel files
    2. Download IPO monthly amount from the same source
    3. Save as data/ipo_monthly.csv and re-run this script
    4. The IPO lag scan will auto-run and show IPO lead/lag dynamics
""")

print("Done. All outputs saved to model/ folder.")
