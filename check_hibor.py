#!/usr/bin/env python3
import sys, warnings
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
import yfinance as yf, pandas as pd

print("=== HIBOR: Not directly available on yfinance ===")
print("HKAB publishes HIBOR but it is not accessible via yfinance tickers.")
print()

# Fed Funds futures -- these ARE available on yfinance and imply forward US rates
# ZQ contracts: ZQMMYY.CBT where MM=month, YY=year
# Price = 100 - implied rate; e.g. price 96.25 => rate 3.75%
print("=== Fed Funds Futures (ZQ) -- best proxy for forward HIBOR ===")
contracts = {
    "ZQN26.CBT": "Jul 2026",
    "ZQU26.CBT": "Sep 2026",
    "ZQZ26.CBT": "Dec 2026",
    "ZQH27.CBT": "Mar 2027",
}
for sym, label in contracts.items():
    try:
        d = yf.download(sym, period="5d", progress=False, auto_adjust=True)
        if len(d) > 0:
            if isinstance(d.columns, pd.MultiIndex):
                d.columns = d.columns.get_level_values(0)
            px = float(d["Close"].dropna().iloc[-1])
            implied = 100 - px
            print(f"  {label} ({sym}): price={px:.3f}  => implied Fed Funds={implied:.2f}%")
        else:
            print(f"  {label} ({sym}): no data")
    except Exception as e:
        print(f"  {label} ({sym}): error - {e}")

print()
print("=== SOFR Futures -- alternative USD rate proxy ===")
sofr_contracts = {
    "SR3U26.CME": "SOFR Sep 2026",
    "SR3Z26.CME": "SOFR Dec 2026",
}
for sym, label in sofr_contracts.items():
    try:
        d = yf.download(sym, period="5d", progress=False, auto_adjust=True)
        if len(d) > 0:
            if isinstance(d.columns, pd.MultiIndex):
                d.columns = d.columns.get_level_values(0)
            px = float(d["Close"].dropna().iloc[-1])
            implied = 100 - px
            print(f"  {label} ({sym}): price={px:.3f}  => implied SOFR={implied:.2f}%")
        else:
            print(f"  {label} ({sym}): no data")
    except Exception as e:
        print(f"  {label} ({sym}): error - {e}")

print()
print("=== Summary ===")
print("HIBOR ~= Fed Funds - 30 to 60bps (HKD peg keeps them tightly linked).")
print("Use ZQ futures to read market-implied forward rates for HIBOR estimate.")
