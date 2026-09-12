from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(r"c:\Users\Arkodeep\Desktop\hackerrank-orchestrate-september26-main\hackerrank-orchestrate-september26-main")
truth = pd.read_csv(ROOT / "dataset" / "sample_requests.csv")
profiles = pd.read_csv(ROOT / "dataset" / "financial_profiles.csv")
events = pd.read_csv(ROOT / "dataset" / "financial_events.csv")
events['settlement_date'] = pd.to_datetime(events['settlement_date'])
rates = pd.read_csv(ROOT / "dataset" / "exchange_rates.csv")
rates['rate_date'] = pd.to_datetime(rates['rate_date'])
messages = pd.read_csv(ROOT / "dataset" / "messages.csv")

def convert(amount, currency, home, date):
    if pd.isna(amount): return 0.0
    amount = float(amount)
    if currency == home or pd.isna(currency): return amount
    d = pd.Timestamp(date)
    exact = rates[(rates.rate_date == d) & (rates.from_currency == currency) & (rates.to_currency == home)]
    if not exact.empty: return amount * float(exact.iloc[0].rate)
    inv = rates[(rates.rate_date == d) & (rates.from_currency == home) & (rates.to_currency == currency)]
    if not inv.empty and float(inv.iloc[0].rate) != 0: return amount / float(inv.iloc[0].rate)
    x = rates[(rates.rate_date <= d) & (rates.from_currency == currency) & (rates.to_currency == home)].sort_values('rate_date')
    if not x.empty: return amount * float(x.iloc[-1].rate)
    x = rates[(rates.rate_date <= d) & (rates.from_currency == home) & (rates.to_currency == currency)].sort_values('rate_date')
    if not x.empty and float(x.iloc[-1].rate) != 0: return amount / float(x.iloc[-1].rate)
    return amount

def next_month_day(year, month, day):
    # advance month
    m = month + 1
    y = year
    if m > 12:
        m = 1
        y += 1
    max_days = pd.Period(f'{y:04d}-{m:02d}').days_in_month
    d = min(day, max_days)
    return pd.Timestamp(year=y, month=m, day=d)

print("Helper functions defined.")
