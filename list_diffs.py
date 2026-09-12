from pathlib import Path
import pandas as pd

ROOT = Path(r"c:\Users\Arkodeep\Desktop\hackerrank-orchestrate-september26-main\hackerrank-orchestrate-september26-main")
samples = pd.read_csv(ROOT / "dataset" / "sample_requests.csv")
profiles = pd.read_csv(ROOT / "dataset" / "financial_profiles.csv")
events = pd.read_csv(ROOT / "dataset" / "financial_events.csv")
events['settlement_date'] = pd.to_datetime(events['settlement_date'])
messages = pd.read_csv(ROOT / "dataset" / "messages.csv")
rates = pd.read_csv(ROOT / "dataset" / "exchange_rates.csv")
rates['rate_date'] = pd.to_datetime(rates['rate_date'])

for idx, r in samples.iterrows():
    p = profiles[profiles.user_id == r.user_id].iloc[0]
    rd = pd.Timestamp(r.request_date)
    bal = p.current_available_balance
    minbal = p.minimum_balance_to_keep
    safe_true = r.amount_safe_to_pay
    slack = bal - minbal
    diff = slack - safe_true
    print(f"Request {r.request_id} ({r.user_id}): bal-min = {slack:.2f}, safe_true = {safe_true:.2f}, diff = {diff:.2f}, req = {r.requested_amount}")
