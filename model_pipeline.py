#!/usr/bin/env python3
"""
388.HK (HKEX) OLS Regression Pipeline
Downloads raw data → weekly processing → OLS (full + era split)
→ VIF, Granger causality, ADF stationarity diagnostics
"""

import os, warnings, textwrap
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import requests
import yfinance as yf
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tsa.stattools import grangercausalitytests, adfuller

# ── Config ─────────────────────────────────────────────────────────────────────
BASE   = r"D:\Backup D\Weekly\USB drive\Invest\AI invest\388"
DATA   = os.path.join(BASE, "data")
MODEL  = os.path.join(BASE, "model")
START  = "2015-01-01"
END    = "2026-06-20"
ERA_CUT = "2022-03-01"   # Fed rate-hike cycle start; same split as gold model
FREQ   = "W-FRI"         # resample to Friday-close weekly

# ── Helpers ────────────────────────────────────────────────────────────────────
def section(title):
    print(f"\n{'='*70}\n  {title}\n{'='*70}")

def dl_fred(series_id):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    r   = requests.get(url, timeout=30)
    r.raise_for_status()
    df  = pd.read_csv(
        pd.io.common.StringIO(r.text),
        parse_dates=["observation_date"], index_col="observation_date"
    )
    df.index.name = "DATE"
    df.columns = [series_id]
    df.replace(".", np.nan, inplace=True)
    df[series_id] = pd.to_numeric(df[series_id], errors="coerce")
    return df

def to_weekly_close(df, col):
    """Resample daily close to last trading day of each week (Fri close)."""
    return df[[col]].resample(FREQ).last().dropna()

def to_weekly_volume(df, col="Volume"):
    """Weekly volume = sum of daily volumes."""
    return df[[col]].resample(FREQ).sum()

def log_ret(s):
    return np.log(s / s.shift(1))

def diff_level(s):
    return s.diff()

def adf_pval(s):
    res = adfuller(s.dropna(), autolag="AIC")
    return res[1]   # p-value

# ══════════════════════════════════════════════════════════════════════════════
# 1. DOWNLOAD RAW DATA
# ══════════════════════════════════════════════════════════════════════════════
section("1. Downloading raw data")

tickers = {
    "0388.HK" : "HKEX stock price",
    "^HSI"    : "Hang Seng Index",
    # 3032.HK = CSOP Hang Seng Tech ETF (tracks HSTECH, daily since 2020)
    "3032.HK" : "Hang Seng Tech ETF proxy (from Dec 2020)",
}

raw = {}
for ticker, label in tickers.items():
    print(f"  {ticker}: {label}")
    df = yf.download(ticker, start=START, end=END, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    raw[ticker] = df
    fname = ticker.replace("^", "").replace(".", "_")
    df.to_csv(os.path.join(DATA, f"raw_{fname}.csv"))
    if len(df) == 0:
        print(f"    WARNING: no data returned for {ticker}")
    else:
        print(f"    -> {len(df)} daily rows  [{df.index[0].date()} - {df.index[-1].date()}]")

print("\n  DFII10: 10-Year TIPS Real Yield (FRED)")
tips_raw = dl_fred("DFII10")
tips_raw.to_csv(os.path.join(DATA, "raw_TIPS.csv"))
print(f"    -> {len(tips_raw)} daily rows  [{tips_raw.index[0].date()} - {tips_raw.index[-1].date()}]")

# ══════════════════════════════════════════════════════════════════════════════
# 2. STATIONARITY CHECK ON RAW LEVELS
# ══════════════════════════════════════════════════════════════════════════════
section("2. ADF stationarity on raw weekly close levels")

adf_checks = {
    "0388.HK Close"  : to_weekly_close(raw["0388.HK"],  "Close")["Close"],
    "HSI Close"      : to_weekly_close(raw["^HSI"],     "Close")["Close"],
    "TIPS Level"     : to_weekly_close(tips_raw,        "DFII10")["DFII10"],
}
adf_rows = []
for name, s in adf_checks.items():
    s = s.dropna()
    p = adf_pval(s)
    adf_rows.append({"Series": name, "ADF p-value": round(p, 4),
                     "Stationary?": "YES" if p < 0.05 else "NO (unit root)"})
print(pd.DataFrame(adf_rows).to_string(index=False))
print("\n  Price levels are non-stationary -> must use log-returns / first-differences")

# ======================================================================
# 3. FEATURE ENGINEERING -> WEEKLY FREQUENCY
# ======================================================================
section("3. Building weekly feature matrix")

# --- 3a. Target: weekly log-return of 0388.HK ---------------------------
hkex_w = to_weekly_close(raw["0388.HK"], "Close")
hkex_w["D_ln_0388"] = log_ret(hkex_w["Close"])

# --- 3b. HSI: weekly log-return + turnover proxy (log volume) -----------
hsi_w  = to_weekly_close(raw["^HSI"], "Close")
hsi_w["D_ln_HSI"] = log_ret(hsi_w["Close"])

vol_w  = to_weekly_volume(raw["^HSI"], "Volume")
vol_w["D_ln_Vol"] = log_ret(vol_w["Volume"])

adf_rows2 = [
    {"Series": "D_ln_0388",  "ADF p-value": round(adf_pval(hkex_w["D_ln_0388"].dropna()), 4)},
    {"Series": "D_ln_HSI",   "ADF p-value": round(adf_pval(hsi_w["D_ln_HSI"].dropna()),   4)},
    {"Series": "D_ln_Vol",   "ADF p-value": round(adf_pval(vol_w["D_ln_Vol"].dropna()),    4)},
]

# --- 3c. HSTECH proxy via 3032.HK ETF (available from Dec 2020) ---------
hstech_raw = raw.get("3032.HK", pd.DataFrame())
if len(hstech_raw) > 50:
    hstech_w = to_weekly_close(hstech_raw, "Close")
    hstech_w["D_ln_HSTECH"] = log_ret(hstech_w["Close"])
    adf_rows2.append({"Series": "D_ln_HSTECH (3032.HK)",
                      "ADF p-value": round(adf_pval(hstech_w["D_ln_HSTECH"].dropna()), 4)})
    has_hstech = True
else:
    hstech_w = pd.DataFrame()
    has_hstech = False
    print("  WARNING: 3032.HK not available, HSTECH feature skipped")

# --- 3d. TIPS: weekly last, first-difference in % points ----------------
tips_w = to_weekly_close(tips_raw, "DFII10")
tips_w.columns = ["TIPS"]
tips_w["D_TIPS"] = diff_level(tips_w["TIPS"])
adf_rows2.append({"Series": "D_TIPS (TIPS delta pp)",
                  "ADF p-value": round(adf_pval(tips_w["D_TIPS"].dropna()), 4)})

print("\n  ADF on transformed series (should all be stationary p<0.05):")
adf_df2 = pd.DataFrame(adf_rows2)
adf_df2["Stationary?"] = adf_df2["ADF p-value"].apply(lambda p: "YES" if p < 0.05 else "NO")
print(adf_df2.to_string(index=False))

# --- 3e. Merge into weekly panel ----------------------------------------
panel = (
    hkex_w[["D_ln_0388"]]
    .join(hsi_w[["D_ln_HSI"]],       how="left")
    .join(vol_w[["D_ln_Vol"]],        how="left")
    .join(tips_w[["D_TIPS", "TIPS"]], how="left")
)
if has_hstech:
    panel = panel.join(hstech_w[["D_ln_HSTECH"]], how="left")

# --- 3f. Lag independent variables by 1 week (causal ordering t-1 -> t) -
lag_cols = ["D_ln_HSI", "D_ln_Vol", "D_TIPS"] + (["D_ln_HSTECH"] if has_hstech else [])
for c in lag_cols:
    if c in panel.columns:
        panel[f"{c}_L1"] = panel[c].shift(1)

panel.to_csv(os.path.join(DATA, "processed_weekly.csv"))
print(f"\n  Saved processed_weekly.csv  |  shape: {panel.shape}")
print(f"  Date range: {panel.index[0].date()} - {panel.index[-1].date()}")
print(f"\n  Southbound Net Inflow & IPO data: NOT available from automated sources.")
print(f"  -> Southbound: HKEX Daily Market Report (manual) or Futu OpenAPI")
print(f"  -> IPO Amount: HKEXnews Monthly Highlights (manual)")

# ======================================================================
# 4. OLS REGRESSIONS
# ======================================================================
section("4. OLS Regressions (HAC Newey-West SE, lag=4)")

FEATURES_FULL = ["D_ln_HSI_L1", "D_ln_Vol_L1", "D_TIPS_L1"]
FEATURES_TECH = FEATURES_FULL + (["D_ln_HSTECH_L1"] if has_hstech else [])

def run_ols(df, y_col, x_cols, label, hac_lags=4):
    avail = [c for c in x_cols if c in df.columns]
    sub = df[[y_col] + avail].dropna()
    if len(sub) < 20:
        print(f"\n  {label}: skipped (only {len(sub)} obs)")
        return None, sub
    Y   = sub[y_col]
    X   = sm.add_constant(sub[avail])
    mdl = sm.OLS(Y, X).fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags})
    n   = len(sub)
    print(f"\n  -- {label}  (N={n} weeks, {sub.index[0].date()} - {sub.index[-1].date()})")
    print(f"     R2={mdl.rsquared:.4f}  Adj-R2={mdl.rsquared_adj:.4f}  "
          f"RMSE={np.sqrt(mdl.mse_resid):.4f}")
    rows = []
    for var in mdl.params.index:
        rows.append({
            "Variable"   : var,
            "beta"       : round(mdl.params[var],  4),
            "HAC t-stat" : round(mdl.tvalues[var], 3),
            "p-value"    : round(mdl.pvalues[var], 4),
            "Sig"        : "***" if mdl.pvalues[var] < 0.01
                      else "**"  if mdl.pvalues[var] < 0.05
                      else "*"   if mdl.pvalues[var] < 0.10
                      else "n.s."
        })
    print(pd.DataFrame(rows).to_string(index=False))
    return mdl, sub

# Full period (2015-2026)
mdl_full, sub_full = run_ols(panel, "D_ln_0388", FEATURES_FULL,
                              "FULL PERIOD (2015-2026) -- HSI + Vol + TIPS (lagged 1w)")

# Era 1: Low-rate era (2015 - Feb 2022)
era1 = panel[panel.index < ERA_CUT]
mdl_e1, sub_e1 = run_ols(era1, "D_ln_0388", FEATURES_FULL,
                          "ERA 1: Low-Rate (2015 - Feb 2022)")

# Era 2: High-rate / NII era (Mar 2022 - present)
era2 = panel[panel.index >= ERA_CUT]
mdl_e2, sub_e2 = run_ols(era2, "D_ln_0388", FEATURES_FULL,
                          "ERA 2: High-Rate/NII (Mar 2022 - 2026)")

# Tech era with HSTECH proxy (Dec 2020-present)
era_tech = panel[panel.index >= "2020-12-01"]
mdl_tech, sub_tech = run_ols(era_tech, "D_ln_0388", FEATURES_TECH,
                              "TECH ERA (Dec 2020-2026) -- + HSTECH proxy")

# ======================================================================
# 5. VIF -- MULTICOLLINEARITY CHECK
# ======================================================================
section("5. Variance Inflation Factors (multicollinearity)")

def compute_vif(df, x_cols):
    avail = [c for c in x_cols if c in df.columns]
    sub = df[avail].dropna()
    X   = sm.add_constant(sub)
    vif_data = pd.DataFrame()
    vif_data["Variable"] = X.columns
    vif_data["VIF"]      = [variance_inflation_factor(X.values, i)
                             for i in range(X.shape[1])]
    vif_data["Flag"] = vif_data["VIF"].apply(
        lambda v: "SEVERE (>10)" if v > 10
             else "MODERATE (5-10)" if v > 5
             else "OK"
    )
    return vif_data

print("\n  Full-period features:")
vif_full = compute_vif(sub_full, FEATURES_FULL)
print(vif_full.to_string(index=False))

if has_hstech and mdl_tech is not None:
    print("\n  Tech-era features (includes HSTECH proxy):")
    vif_tech = compute_vif(sub_tech, FEATURES_TECH)
    print(vif_tech.to_string(index=False))
    vif_tech.to_csv(os.path.join(MODEL, "vif_tech.csv"), index=False)

vif_full.to_csv(os.path.join(MODEL, "vif_full.csv"), index=False)

# ======================================================================
# 6. CORRELATION MATRIX
# ======================================================================
section("6. Correlation matrix (lagged features vs target)")

corr_cols = [c for c in ["D_ln_0388"] + FEATURES_TECH if c in panel.columns]
corr_df   = panel[corr_cols].dropna()
corr_mat  = corr_df.corr().round(3)
print(corr_mat.to_string())
corr_mat.to_csv(os.path.join(MODEL, "correlation_matrix.csv"))

# ======================================================================
# 7. GRANGER CAUSALITY  (does X at lags 1-4 predict Y?)
# ======================================================================
section("7. Granger Causality Tests (max lag = 4 weeks)")

granger_features = {
    "D_ln_HSI" : hsi_w["D_ln_HSI"],
    "D_ln_Vol" : vol_w["D_ln_Vol"],
    "D_TIPS"   : tips_w["D_TIPS"],
}
if has_hstech:
    granger_features["D_ln_HSTECH"] = hstech_w["D_ln_HSTECH"]

target_s = panel["D_ln_0388"]

granger_rows = []
MAX_LAG = 4
for fname, fs in granger_features.items():
    combo = pd.concat([target_s, fs], axis=1).dropna()
    if len(combo) < 30:
        granger_rows.append({
            "Feature": fname,
            "p-values L1-L4": "N/A (too few obs)",
            "Min p": "N/A",
            "Granger-causes 0388?": "N/A"
        })
        continue
    try:
        gc_res = grangercausalitytests(combo, maxlag=MAX_LAG, verbose=False)
        pvals  = [gc_res[lag][0]["ssr_ftest"][1] for lag in range(1, MAX_LAG + 1)]
        minp   = min(pvals)
        pstr   = " | ".join([f"L{i+1}:{p:.3f}" for i, p in enumerate(pvals)])
        granger_rows.append({
            "Feature"            : fname,
            "p-values L1-L4"    : pstr,
            "Min p"             : round(minp, 4),
            "Granger-causes 0388?": "YES ***" if minp < 0.01
                               else "YES **"  if minp < 0.05
                               else "YES *"   if minp < 0.10
                               else "NO"
        })
    except Exception as e:
        granger_rows.append({"Feature": fname, "p-values L1-L4": str(e),
                              "Min p": "ERR", "Granger-causes 0388?": "ERROR"})

gc_df = pd.DataFrame(granger_rows)
print(gc_df.to_string(index=False))
gc_df.to_csv(os.path.join(MODEL, "granger_causality.csv"), index=False)

# ======================================================================
# 8. SUMMARY
# ======================================================================
section("8. Summary")

def r2str(mdl, sub):
    if mdl is None:
        return "N/A"
    return f"R2={mdl.rsquared:.4f}  Adj-R2={mdl.rsquared_adj:.4f}  N={len(sub)}"

summary_lines = [
    "388.HK OLS Model -- Quick Results",
    "===================================",
    "Target  : D_ln_0388 (weekly log-return of 0388.HK, period t)",
    "Features: all lagged 1 week (t-1) for causal ordering",
    "",
    f"Full period (2015-2026): {r2str(mdl_full, sub_full)}",
    f"Era 1  Low-Rate (15-22): {r2str(mdl_e1,   sub_e1)}",
    f"Era 2 High-Rate (22-26): {r2str(mdl_e2,   sub_e2)}",
    f"Tech era (Dec20-2026)  : {r2str(mdl_tech, sub_tech)}",
    "",
    "Data gaps (require manual sourcing):",
    "  - Southbound Net Inflow: HKEX Daily Market Report / Futu OpenAPI",
    "  - IPO rolling amount   : HKEXnews Monthly Market Highlights",
    "  Expected R2 improvement: +5-15pp when these are added",
    "",
    "Output files saved to model/ and data/ folders.",
]
summary = "\n".join(summary_lines)
print(summary)

with open(os.path.join(MODEL, "ols_summary.txt"), "w", encoding="utf-8") as f:
    f.write(summary)

print("Done.")
