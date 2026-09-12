from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(r"c:\Users\Arkodeep\Desktop\hackerrank-orchestrate-september26-main\hackerrank-orchestrate-september26-main")
samples = pd.read_csv(ROOT / "dataset" / "sample_requests.csv")
profiles = pd.read_csv(ROOT / "dataset" / "financial_profiles.csv")
events = pd.read_csv(ROOT / "dataset" / "financial_events.csv")
events['settlement_date'] = pd.to_datetime(events['settlement_date'])
events['event_date'] = pd.to_datetime(events['event_date'])
rates = pd.read_csv(ROOT / "dataset" / "exchange_rates.csv")
rates['rate_date'] = pd.to_datetime(rates['rate_date'])

def convert(amount, currency, home, date):
    if pd.isna(amount): return 0.0
    amount = float(amount)
    if pd.isna(currency) or currency == home: return amount
    d = pd.Timestamp(date)
    x = rates[(rates.rate_date == d) & (rates.from_currency == currency) & (rates.to_currency == home)]
    if not x.empty: return amount * float(x.iloc[0].rate)
    x = rates[(rates.rate_date == d) & (rates.from_currency == home) & (rates.to_currency == currency)]
    if not x.empty and float(x.iloc[0].rate): return amount / float(x.iloc[0].rate)
    x = rates[(rates.rate_date <= d) & (rates.from_currency == currency) & (rates.to_currency == home)].sort_values('rate_date')
    if not x.empty: return amount * float(x.iloc[-1].rate)
    x = rates[(rates.rate_date <= d) & (rates.from_currency == home) & (rates.to_currency == currency)].sort_values('rate_date')
    if not x.empty and float(x.iloc[-1].rate): return amount / float(x.iloc[-1].rate)
    return amount

# Check sample 1 to 25: what is the minimum balance dip under various assumptions?
for idx in range(25):
    r = samples.iloc[idx]
    prof = profiles[profiles.user_id == r.user_id].iloc[0]
    rd = pd.Timestamp(r.request_date)
    bal = prof.current_available_balance
    minbal = prof.minimum_balance_to_keep
    safe_true = r.amount_safe_to_pay
    
    # Let's inspect user events
    ue = events[events.user_id == r.user_id].sort_values('settlement_date')
    
    # Check explicit future events
    future_ue = ue[(ue.settlement_date >= rd) & (ue.settlement_date <= rd + pd.Timedelta(days=90))]
    
    print(f"Sample {r.request_id} ({r.user_id}): rd={rd.date()}, bal={bal}, minbal={minbal}, bal-min={bal-minbal:.2f}, safe_true={safe_true}, req={r.requested_amount}")
