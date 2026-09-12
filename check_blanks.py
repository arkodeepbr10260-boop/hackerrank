from pathlib import Path
import pandas as pd
import numpy as np
import re
from itertools import combinations

ROOT = Path(r"c:\Users\Arkodeep\Desktop\hackerrank-orchestrate-september26-main\hackerrank-orchestrate-september26-main")
truth = pd.read_csv(ROOT / "dataset" / "sample_requests.csv")
profiles = pd.read_csv(ROOT / "dataset" / "financial_profiles.csv")
events = pd.read_csv(ROOT / "dataset" / "financial_events.csv")
events['settlement_date'] = pd.to_datetime(events['settlement_date'], errors='coerce')
events['event_date'] = pd.to_datetime(events['event_date'], errors='coerce')
rates = pd.read_csv(ROOT / "dataset" / "exchange_rates.csv")
rates['rate_date'] = pd.to_datetime(rates['rate_date'], errors='coerce')
messages = pd.read_csv(ROOT / "dataset" / "messages.csv")
options = pd.read_csv(ROOT / "dataset" / "request_payment_options.csv")
options['first_payment_date'] = pd.to_datetime(options['first_payment_date'], errors='coerce')
images = pd.read_csv(ROOT / "dataset" / "images.csv")

# Fill blank amounts from images if needed (or check if any are blank)
print("Blank amounts in events:", events['amount'].isna().sum())
if events['amount'].isna().any():
    for idx, row in events[events.amount.isna()].iterrows():
        print(f"Blank amount: {row.event_id} user={row.user_id}")
