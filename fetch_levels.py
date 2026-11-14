"""
Computes next Weekly/Daily Buy (green = pivot low) and Sell (red = pivot high)
levels for Nifty 50 stocks, replicating the Pine logic:
  - pivots: ta.pivothigh/pivotlow(left=2, right=2) on the higher timeframe
  - a level is "active" until a candle CLOSES through it
  - Buy level  = nearest active green level BELOW current price
  - Sell level = nearest active red level ABOVE current price
"""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

LEFT_BARS = 2
RIGHT_BARS = 2

NIFTY50 = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BHARTIARTL",
    "BPCL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY",
    "EICHERMOT", "ETERNAL", "GRASIM", "HCLTECH", "HDFCBANK",
    "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK",
    "ITC", "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK",
    "LT", "M&M", "MARUTI", "NESTLEIND", "NTPC",
    "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN",
    "SBIN", "SUNPHARMA", "TCS", "TATACONSUM", "TMPV",
    "TATASTEEL", "TECHM", "TITAN", "TRENT", "ULTRACEMCO", "WIPRO",
]
# Verify this list against the current NSE Nifty 50 constituents.


def clean(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["High", "Low", "Close"])
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=["High", "Low", "Close"])


def fetch(symbol: str, interval: str, period: str) -> pd.DataFrame:
    df = yf.download(f"{symbol}.NS", interval=interval, period=period,
                     auto_adjust=False, progress=False)
    return clean(df)


def find_levels(df: pd.DataFrame):
    """Return list of dicts: {price, side, confirm_idx}. side: +1 green (low), -1 red (high)."""
    if df.empty:
        return []
    highs, lows = df["High"].values, df["Low"].values
    n = len(df)
    levels = []
    for i in range(LEFT_BARS, n - RIGHT_BARS):
        lo, hi = i - LEFT_BARS, i + RIGHT_BARS + 1
        if highs[i] == highs[lo:hi].max():
            levels.append({"price": float(highs[i]), "side": -1, "confirm": i + RIGHT_BARS})
        if lows[i] == lows[lo:hi].min():
            levels.append({"price": float(lows[i]), "side": 1, "confirm": i + RIGHT_BARS})
    return levels


def next_levels(df: pd.DataFrame):
    if df.empty:
        return None, None, None
    closes = df["Close"].values
    cmp = float(closes[-1])
    last = len(df) - 1
    active = []
    for lv in find_levels(df):
        broke = False
        for j in range(lv["confirm"] + 1, last + 1):
            if (lv["side"] == 1 and closes[j] < lv["price"]) or \
               (lv["side"] == -1 and closes[j] > lv["price"]):
                broke = True
                break
        if not broke:
            active.append(lv)

    greens_below = [l["price"] for l in active if l["side"] == 1 and l["price"] < cmp]
    reds_above = [l["price"] for l in active if l["side"] == -1 and l["price"] > cmp]
    buy = max(greens_below) if greens_below else None
    sell = min(reds_above) if reds_above else None
    return cmp, buy, sell


def r(x):
    return round(x, 2) if x is not None else None


def main():
    rows = []
    for idx, name in enumerate(NIFTY50, start=1):
        try:
            d_daily = fetch(name, "1d", "2y")
            d_weekly = fetch(name, "1wk", "5y")
            if d_daily.empty or d_weekly.empty:
                print(f"NO DATA {name}")
                rows.append({"sno": idx, "name": name, "cmp": None,
                             "weekly_buy": None, "weekly_sell": None,
                             "daily_buy": None, "daily_sell": None})
                continue
            cmp, wb, ws = next_levels(d_weekly)
            cmp_d, db, ds = next_levels(d_daily)
            rows.append({
                "sno": idx, "name": name, "cmp": r(cmp_d),
                "weekly_buy": r(wb), "weekly_sell": r(ws),
                "daily_buy": r(db), "daily_sell": r(ds),
            })
            print(f"OK   {name}")
        except Exception as e:
            print(f"FAIL {name}: {e}")
            rows.append({"sno": idx, "name": name, "cmp": None,
                         "weekly_buy": None, "weekly_sell": None,
                         "daily_buy": None, "daily_sell": None})

    stamp = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d-%b-%Y %H:%M IST")
    with open("docs/data.json", "w") as f:
        json.dump({"updated": stamp, "rows": rows}, f, indent=2)
    print("Wrote docs/data.json")


if __name__ == "__main__":
    main()