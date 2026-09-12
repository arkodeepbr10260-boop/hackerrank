from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(r"c:\Users\Arkodeep\Desktop\hackerrank-orchestrate-september26-main\hackerrank-orchestrate-september26-main")
truth = pd.read_csv(ROOT / "dataset" / "sample_requests.csv")
profiles = pd.read_csv(ROOT / "dataset" / "financial_profiles.csv")
events = pd.read_csv(ROOT / "dataset" / "financial_events.csv")
events['settlement_date'] = pd.to_datetime(events['settlement_date'], errors='coerce')
events['event_date'] = pd.to_datetime(events['event_date'], errors='coerce')
rates = pd.read_csv(ROOT / "dataset" / "exchange_rates.csv")
rates['rate_date'] = pd.to_datetime(rates['rate_date'], errors='coerce')

IMAGE_AMOUNTS = {
    'event_253': 4365000.0,
    'event_1442': 100000.0,
    'event_1545': 41272.0,
    'event_1700': 2854.0,
    'event_1786': 704.05,
    'event_3051': 1995.0,
    'event_3231': 8528.0,
    'event_4535': 15339.0,
    'event_5170': 723.0,
    'event_6033': 79679.26,
    'event_6859': 3650.0,
    'event_7307': 33.50,
    'event_7941': 2298.0,
    'event_9421': 4543.0,
    'event_9806': 9968.0,
    'event_10521': 393.22,
}

for eid, amt in IMAGE_AMOUNTS.items():
    events.loc[events.event_id == eid, 'amount'] = amt

print("Filled missing amounts. NaN count:", events.amount.isna().sum())
