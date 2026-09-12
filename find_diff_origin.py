from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(r"c:\Users\Arkodeep\Desktop\hackerrank-orchestrate-september26-main\hackerrank-orchestrate-september26-main")
events = pd.read_csv(ROOT / "dataset" / "financial_events.csv")
events['settlement_date'] = pd.to_datetime(events['settlement_date'])
events['event_date'] = pd.to_datetime(events['event_date'])
rates = pd.read_csv(ROOT / "dataset" / "exchange_rates.csv")
profiles = pd.read_csv(ROOT / "dataset" / "financial_profiles.csv")

diffs = {
    'user_08': 452.00,
    'user_14': 1134.00,
    'user_15': 487.00,
    'user_17': 140430.00,
    'user_18': 624.00,
    'user_21': 568.00,
    'user_22': 157.00,
    'user_24': 20625.00,
    'user_25': 7258950.00
}

for uid, target in diffs.items():
    ue = events[events.user_id == uid]
    print(f"\nSearching for target {target} in {uid}:")
    # check single events
    match1 = ue[ue.amount == target]
    if not match1.empty:
        print("  Exact single event match:")
        print(match1[['event_id', 'settlement_date', 'amount', 'category', 'description']])
    
    # check sum of combinations of debit events
    debits = ue[ue.direction == 'debit'].dropna(subset=['amount'])
    unique_amts = debits.amount.unique()
    found = False
    from itertools import combinations
    for k in range(1, 6):
        for combo in combinations(unique_amts, k):
            if abs(sum(combo) - target) < 0.01:
                print(f"  Combo of {k} amounts: {combo}")
                for a in combo:
                    rows = debits[debits.amount == a]
                    print(f"     {a}: {rows.category.iloc[0]} ({rows.description.iloc[0]})")
                found = True
                break
        if found: break
