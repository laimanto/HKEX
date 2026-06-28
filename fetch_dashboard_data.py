#!/usr/bin/env python3
"""
Fetches all historical data needed for the HKEX valuation dashboard.
Outputs: data/dashboard_data.json
"""
import sys, os, json, warnings, time
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
import yfinance as yf
import requests

BASE  = r"D:\Backup D\Weekly\USB drive\Invest\AI invest\388"
DATA  = os.path.join(BASE, "data")
os.makedirs(DATA, exist_ok=True)

def to_monthly(df, col, agg="last"):
    s = df[col].dropna()
    if agg == "last":  return s.resample("MS").last().dropna()
    if agg == "mean":  return s.resample("MS").mean().dropna()

def series_to_js(s, decimals=2):
    dates  = [d.strftime("%Y-%m-%d") for d in s.index]
    values = [round(float(v), decimals) if not np.isnan(v) else None for v in s.values]
    return dates, values

print("=" * 60)
print("  HKEX Dashboard Data Fetcher")
print("=" * 60)

# ── 1. HKEX PRICE (0388.HK) ─────────────────────────────────
print("\n[1] Downloading 0388.HK price history...")
raw = yf.download("0388.HK", start="2000-01-01", auto_adjust=True, progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.get_level_values(0)
price_m = to_monthly(raw, "Close")
price_dates, price_vals = series_to_js(price_m, 1)
_last = raw["Close"].dropna()
current_price = round(float(_last.iloc[-1]), 1)
current_date  = _last.index[-1].strftime("%Y-%m-%d")
print(f"   {len(price_m)} monthly obs  |  latest: {current_date} = HKD {current_price}")

# ── 2. HIBOR (3-month) from FRED ────────────────────────────
print("\n[2] Downloading HIBOR from FRED...")
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"

hibor = None
for series in ["IR3TIB01HKM156N", "INTDSGHKM193N"]:
    try:
        r = requests.get(FRED_URL.format(series), timeout=15)
        from io import StringIO
        df = pd.read_csv(StringIO(r.text), parse_dates=["DATE"], index_col="DATE")
        df.columns = ["HIBOR"]
        df["HIBOR"] = pd.to_numeric(df["HIBOR"], errors="coerce")
        df = df[df["HIBOR"] > 0].dropna()
        if len(df) > 20:
            hibor = df["HIBOR"].resample("MS").last().dropna()
            print(f"   Series {series}: {len(hibor)} obs  |  latest: {hibor.index[-1].date()} = {hibor.iloc[-1]:.2f}%")
            break
    except Exception as e:
        print(f"   {series}: FAILED ({e})")

if hibor is None:
    # Fallback: approximate from FEDFUNDS (HIBOR ≈ FF - 40bps)
    print("   Fallback: approximating HIBOR from FEDFUNDS - 0.40%")
    ff = pd.read_csv(os.path.join(DATA, "raw_FEDFUNDS.csv"), index_col=0, parse_dates=True)
    ff.columns = ["FF"]
    hibor = (ff["FF"] - 0.40).clip(lower=0).resample("MS").last().dropna()

hibor_dates, hibor_vals = series_to_js(hibor, 2)
print(f"   HIBOR series: {len(hibor)} monthly obs")

# ── 3. HK MARKET ADT ────────────────────────────────────────
print("\n[3] Downloading HK market daily turnover from HKEX...")

# Fallback: annual ADT (HKD bn/day) compiled from HKEX annual reports.
# Used when live download fails. 2026 = estimate.
ADT_FALLBACK = {
    2000:  8.0, 2001:  7.0, 2002:  7.0, 2003:  8.0, 2004: 11.0,
    2005: 15.0, 2006: 24.0, 2007: 80.0, 2008: 55.0, 2009: 44.0,
    2010: 60.0, 2011: 62.0, 2012: 54.0, 2013: 57.0, 2014: 65.0,
    2015:107.0, 2016: 68.0, 2017: 85.0, 2018:103.0, 2019: 88.0,
    2020:107.0, 2021:167.0, 2022:105.0, 2023: 90.0, 2024:120.0,
    2025:249.8, 2026:275.0,
}

def try_fetch_hkex_adt():
    """
    Try to download annual ADT directly from HKEX.
    Strategy 1: old static HKEX HTML page (no JS, legacy URL).
    Strategy 2: guessed Excel URL patterns from HKEX media server.
    Returns {year: adt_bn_per_day} or {} on failure.
    """
    import io
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.hkex.com.hk/",
    }

    # Strategy 1: old static HKEX annual turnover page
    try:
        r = requests.get(
            "https://www.hkex.com.hk/eng/stat/smstat/turnover/a_turnover.htm",
            headers=hdrs, timeout=15)
        if r.status_code == 200 and len(r.text) > 2000:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, "html.parser")
            result = {}
            for table in soup.find_all("table"):
                for row in table.find_all("tr"):
                    cells = [c.get_text(strip=True).replace(",", "").replace("$", "")
                             for c in row.find_all(["td", "th"])]
                    for i, cell in enumerate(cells):
                        try:
                            yr = int(cell)
                            if 2000 <= yr <= 2030:
                                for cand in cells[i+1:]:
                                    try:
                                        num = float(cand)
                                        if 500 < num < 200000:    # total annual turnover HKD bn
                                            result[yr] = round(num / 250, 1)
                                            break
                                        elif 1 < num < 1000:      # already ADT HKD bn/day
                                            result[yr] = round(num, 1)
                                            break
                                    except ValueError:
                                        pass
                        except (ValueError, IndexError):
                            pass
            if len(result) >= 10:
                print(f"   HKEX static page: parsed {len(result)} years of ADT data")
                return result
            else:
                print(f"   HKEX static page returned but only parsed {len(result)} years (page may need JS)")
    except Exception as e:
        print(f"   HKEX static page error: {e}")

    # Strategy 2: try guessed Excel URL patterns on HKEX media server
    cur_yr = pd.Timestamp.now().year
    url_patterns = [
        "https://www.hkex.com.hk/-/media/HKEX-Market/Market-Data/Statistics/Consolidated-Exchange-Statistics/Securities-Statistics/Turnover/Annual/a_turnover_{y}.xls",
        "https://www.hkex.com.hk/-/media/HKEX-Market/Market-Data/Statistics/Consolidated-Exchange-Statistics/Securities-Statistics/Turnover/Annual/se_stk_mrkt_annual_{y}.xlsx",
    ]
    for y in range(cur_yr, cur_yr - 3, -1):
        for pat in url_patterns:
            url = pat.format(y=y)
            try:
                r = requests.get(url, headers=hdrs, timeout=20)
                if r.status_code == 200 and len(r.content) > 5000:
                    xl = pd.read_excel(io.BytesIO(r.content), sheet_name=0, header=None)
                    result = {}
                    for _, row in xl.iterrows():
                        cells = [str(c) for c in row.dropna()]
                        for i, cell in enumerate(cells):
                            try:
                                yr_val = int(float(cell))
                                if 2000 <= yr_val <= 2030:
                                    for cand in cells[i+1:]:
                                        try:
                                            num = float(cand.replace(",", ""))
                                            if 1 < num < 1000:
                                                result[yr_val] = round(num, 1)
                                                break
                                        except ValueError:
                                            pass
                            except (ValueError, TypeError):
                                pass
                    if len(result) >= 5:
                        print(f"   Downloaded HKEX Excel from: {url}")
                        print(f"   Parsed {len(result)} years of ADT data")
                        return result
            except Exception:
                pass
    return {}

web_adt = try_fetch_hkex_adt()
ADT_ANNUAL = dict(ADT_FALLBACK)
if web_adt:
    for yr, val in web_adt.items():
        if yr <= 2024:          # keep confirmed 2025 result and 2026 estimate locked
            ADT_ANNUAL[yr] = val
    print(f"   HKEX web: updated {sum(1 for y in web_adt if y <= 2024)} historical years")
else:
    print("   Using compiled ADT table (HKEX annual reports + confirmed 2025 result)")

# Annual series for bar chart — year strings as labels
adt_years = sorted(ADT_ANNUAL.keys())
adt_dates = [str(y) for y in adt_years]
adt_vals  = [round(float(ADT_ANNUAL[y]), 1) for y in adt_years]
print(f"   ADT series: {len(adt_years)} annual data points ({adt_years[0]}–{adt_years[-1]})")

# Date grid needed for EPS/P/E interpolation below
all_months = pd.date_range(start="2000-01-01", end=pd.Timestamp.today(), freq="MS")

# ── 4. ANNUAL IPO PROCEEDS ──────────────────────────────────
print("\n[4] Loading annual IPO data...")
# Source: HKEX Annual Statistics, SFC reports, Bloomberg
# HKD bn raised in HK IPOs each year
IPO_ANNUAL = {
    2000: 130.0, 2001: 25.0,  2002: 30.0,  2003: 35.0,  2004: 90.0,
    2005: 195.0, 2006: 335.0, 2007: 276.0, 2008: 65.0,  2009: 245.0,
    2010: 449.0, 2011: 261.0, 2012: 88.0,  2013: 168.0, 2014: 228.0,
    2015: 262.0, 2016: 195.0, 2017: 128.0, 2018: 286.0, 2019: 314.0,
    2020: 397.0, 2021: 334.0, 2022: 104.0, 2023: 46.0,  2024: 87.0,
    2025: 80.0,  2026: 120.0,
}
ipo_rows = []
for yr, val in sorted(IPO_ANNUAL.items()):
    ipo_rows.append({"date": pd.Timestamp(f"{yr}-06-01"), "ipo": val})
ipo_df = pd.DataFrame(ipo_rows).set_index("date")["ipo"]
ipo_dates = [d.strftime("%Y-%m-%d") for d in ipo_df.index]
ipo_vals  = [float(v) for v in ipo_df.values]
print(f"   IPO data: {len(ipo_df)} annual data points (2000-2026)")

# ── 5. HISTORICAL P/E ───────────────────────────────────────
print("\n[5] Computing historical P/E...")
# Annual EPS from HKEX income statements (yfinance + historical)
# Source: HKEX Annual Reports; 2000-2021 approximate
EPS_ANNUAL = {
    2000: 0.95, 2001: 0.50, 2002: 0.62, 2003: 0.75, 2004: 1.05,
    2005: 1.45, 2006: 2.20, 2007: 3.90, 2008: 3.20, 2009: 3.50,
    2010: 4.20, 2011: 4.50, 2012: 4.10, 2013: 4.80, 2014: 5.30,
    2015: 7.20, 2016: 5.90, 2017: 6.80, 2018: 7.50, 2019: 7.61,
    2020: 8.05, 2021: 9.28, 2022: 7.95, 2023: 9.36, 2024: 10.29,
    2025: 14.01,
}
# Build monthly EPS by interpolation
eps_rows = [{"date": pd.Timestamp(f"{yr}-06-01"), "eps": v}
            for yr, v in sorted(EPS_ANNUAL.items())]
eps_s = pd.DataFrame(eps_rows).set_index("date")["eps"]
eps_m = eps_s.reindex(all_months, method=None).interpolate(method="time").dropna()

# P/E = monthly price / interpolated EPS
pe_m = pd.Series(index=price_m.index, dtype=float)
for dt in price_m.index:
    if dt in eps_m.index:
        e = eps_m[dt]
        if e and e > 0:
            pe_m[dt] = price_m[dt] / e

pe_m = pe_m.replace([np.inf, -np.inf], np.nan).dropna()
pe_m = pe_m.clip(0, 80)   # cap outliers
pe_dates, pe_vals = series_to_js(pe_m, 1)
print(f"   P/E series: {len(pe_m)} monthly obs  |  range: {pe_m.min():.1f}x – {pe_m.max():.1f}x")
pe_25 = float(np.percentile(pe_m[pe_m.index.year >= 2015], 25))
pe_50 = float(np.percentile(pe_m[pe_m.index.year >= 2015], 50))
pe_75 = float(np.percentile(pe_m[pe_m.index.year >= 2015], 75))
print(f"   Recent P/E percentiles (2015+): 25th={pe_25:.1f}x, median={pe_50:.1f}x, 75th={pe_75:.1f}x")

# ── 6. FED FUNDS FUTURES (live rate forecasts) ──────────────
print("\n[6] Fetching Fed Funds futures for HIBOR forecast...")
futures_map = {
    "ZQN26.CBT": "Jul 2026",
    "ZQU26.CBT": "Sep 2026",
    "ZQZ26.CBT": "Dec 2026",
}
futures_rates = {}
for sym, label in futures_map.items():
    try:
        d = yf.download(sym, period="5d", progress=False, auto_adjust=True)
        if len(d) > 0:
            if isinstance(d.columns, pd.MultiIndex):
                d.columns = d.columns.get_level_values(0)
            px   = float(d["Close"].dropna().iloc[-1])
            rate = round(100 - px, 2)
            futures_rates[label] = {"ff": rate, "hibor": round(rate - 0.40, 2)}
    except Exception:
        pass
print(f"   Futures: {futures_rates}")

# Derive consensus HIBOR
current_ff = float(hibor.iloc[-1]) if len(hibor) > 0 else 3.0
h2_ff = futures_rates.get("Dec 2026", {}).get("ff", current_ff)
avg_ff = (current_ff + 0.40 + h2_ff) / 2    # approx H1 + H2 blend (HIBOR basis)
consensus_hibor = round(avg_ff - 0.40, 2)

# ── 7. ANALYST DATA ─────────────────────────────────────────
print("\n[7] Fetching analyst data from yfinance...")
try:
    t = yf.Ticker("0388.HK")
    info = t.info
    analyst_target_mean   = info.get("targetMeanPrice",   518.0)
    analyst_target_high   = info.get("targetHighPrice",   610.0)
    analyst_target_low    = info.get("targetLowPrice",    400.0)
    analyst_n             = info.get("numberOfAnalystOpinions", 17)
    ttm_eps               = info.get("trailingEps",  14.71)
    fwd_eps               = info.get("forwardEps",   15.63)
    fwd_pe                = info.get("forwardPE",    24.0)
    trailing_pe_live      = info.get("trailingPE",   None)
    print(f"   TTM EPS={ttm_eps}  Fwd EPS={fwd_eps}  Target={analyst_target_mean}")
    print(f"   Analysts: {analyst_n}  |  Target range: {analyst_target_low}-{analyst_target_high}")
except Exception as e:
    print(f"   yfinance analyst data failed: {e}")
    analyst_target_mean = 518.0; analyst_target_high = 610.0; analyst_target_low = 400.0
    analyst_n = 17; ttm_eps = 14.71; fwd_eps = 15.63; fwd_pe = 24.0
    trailing_pe_live = 25.5

# Analyst-implied ADT (back-calculate from fwd_eps)
# Target revenue needed for fwd_eps:
# TRADING_K recalibrated: 2025 ADT=250bn, Trading+Clearing rev=11,800mn
# TRADING_K = 11800/250 = 47.2  (HKDmn per HKDbn ADT per year)
OPEX = 9000; SHARES = 1267; TRADING_K = 47.2; NII_K = 2700
IPO_BASE = 620; IPO_K = 8.0; DATA_R = 1050; OTHER_R = 1100

# Prefill: user's 2026 estimates (275bn ADT, HIBOR futures consensus, IPO recovery)
analyst_adt   = 275.0   # user's 2026 ADT estimate (HKDbn/day)
analyst_hibor = 3.5     # HIBOR consensus from futures
analyst_ipo   = 120.0   # IPO recovery estimate (HKDbn/yr)
analyst_pe    = round(pe_50, 0)   # USE MEDIAN P/E as default per user instruction
print(f"   Model prefill: ADT={analyst_adt}bn  HIBOR={analyst_hibor}%  IPO={analyst_ipo}bn  P/E={analyst_pe}x (median)")

# ── 8. SAVE JSON ────────────────────────────────────────────
print("\n[8] Saving dashboard_data.json...")
out = {
    "meta": {
        "generated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
        "current_price": current_price,
        "current_date": current_date,
        "ttm_eps": ttm_eps,
        "fwd_eps": fwd_eps,
        "analyst_target_mean": analyst_target_mean,
        "analyst_target_high": analyst_target_high,
        "analyst_target_low": analyst_target_low,
        "analyst_n": analyst_n,
        "trailing_pe_live": trailing_pe_live,
        "consensus_hibor": consensus_hibor,
    },
    "model_constants": {
        "TRADING_K": TRADING_K,  # mn per HKDbn ADT per year; recalib 2025: 11800/250=47.2
        "NII_K": NII_K,
        "IPO_BASE": IPO_BASE,
        "IPO_K": IPO_K,
        "DATA_REV": DATA_R,
        "OTHER_REV": OTHER_R,
        "OPEX": OPEX,
        "SHARES_MN": SHARES,
        "PE_LOW":    round(pe_25, 1),
        "PE_MEDIAN": round(pe_50, 1),
        "PE_HIGH":   round(pe_75 * 1.10, 1),
    },
    "prefill": {
        "adt":   float(analyst_adt),
        "hibor": analyst_hibor,
        "ipo":   float(analyst_ipo),
        "pe":    float(analyst_pe),   # median P/E
    },
    "futures": futures_rates,
    "series": {
        "price": {"dates": price_dates, "values": price_vals, "label": "0388.HK Close (HKD)", "unit": "HKD"},
        "hibor": {"dates": hibor_dates, "values": hibor_vals, "label": "3M HIBOR (%)", "unit": "%"},
        "adt":   {"dates": adt_dates,   "values": adt_vals,   "label": "HK Market ADT (HKD bn/day)", "unit": "HKDbn"},
        "ipo":   {"dates": ipo_dates,   "values": ipo_vals,   "label": "HK IPO Proceeds (HKD bn/yr)", "unit": "HKDbn"},
        "pe":    {"dates": pe_dates,    "values": pe_vals,    "label": "HKEX Trailing P/E (x)", "unit": "x"},
    },
    "ipo_annual": {str(yr): val for yr, val in IPO_ANNUAL.items()},
    "eps_annual":  {str(yr): val for yr, val in EPS_ANNUAL.items()},
}

out_path = os.path.join(DATA, "dashboard_data.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)

print(f"   Saved: {out_path}  ({os.path.getsize(out_path)//1024}KB)")
print("\nDone. Run build_dashboard.py next to generate HTML.")
