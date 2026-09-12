from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(r"c:\Users\Arkodeep\Desktop\hackerrank-orchestrate-september26-main\hackerrank-orchestrate-september26-main")
truth = pd.read_csv(ROOT / "dataset" / "sample_requests.csv")
profiles = pd.read_csv(ROOT / "dataset" / "financial_profiles.csv")
events = pd.read_csv(ROOT / "dataset" / "financial_events.csv")
events['settlement_date'] = pd.to_datetime(events['settlement_date'])
events['event_date'] = pd.to_datetime(events['event_date'])
rates = pd.read_csv(ROOT / "dataset" / "exchange_rates.csv")
rates['rate_date'] = pd.to_datetime(rates['rate_date'])

# Let's inspect each sample request to see if d < request_date was causing issues
for idx in range(25):
    r = truth.iloc[idx]
    prof = profiles[profiles.user_id == r.user_id].iloc[0]
    rd = pd.Timestamp(r.request_date)
    # Check events around rd
    past_settled = events[(events.user_id == r.user_id) & (events.settlement_date <= rd) & (events.status == 'settled')]
    # recurring monthly items
    for (d, cat, desc), g in past_settled.groupby(['direction', 'category', 'description']):
        if len(g) >= 3:
            gaps = g.settlement_date.diff().dt.days.dropna()
            med = gaps.median()
            if 25 <= med <= 35:
                next_d = g.settlement_date.iloc[-1] + pd.Timedelta(days=int(round(med)))
                if next_d < rd:
                    print(f"Sample {r.request_id} ({r.user_id}): {cat} ({desc}) last={g.settlement_date.iloc[-1].date()}, next={next_d.date()} < rd={rd.date()}!")
