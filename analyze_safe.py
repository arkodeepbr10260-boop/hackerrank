from pathlib import Path
import pandas as pd

ROOT = Path(r"c:\Users\Arkodeep\Desktop\hackerrank-orchestrate-september26-main\hackerrank-orchestrate-september26-main")
samples = pd.read_csv(ROOT / "dataset" / "sample_requests.csv")
profiles = pd.read_csv(ROOT / "dataset" / "financial_profiles.csv")
events = pd.read_csv(ROOT / "dataset" / "financial_events.csv")
for c in ['event_date', 'settlement_date']:
    events[c] = pd.to_datetime(events[c], errors='coerce')

for idx, r in samples.iterrows():
    p = profiles[profiles.user_id == r.user_id].iloc[0]
    rd = pd.Timestamp(r.request_date)
    bal = p.current_available_balance
    minbal = p.minimum_balance_to_keep
    safe_true = r.amount_safe_to_pay
    slack = bal - minbal
    
    # Find events between request_date and next salary
    user_events = events[events.user_id == r.user_id].sort_values('settlement_date')
    future_sal = user_events[(user_events.settlement_date >= rd) & (user_events.category == 'salary') & (user_events.direction == 'credit')]
    next_sal_date = future_sal.iloc[0].settlement_date if not future_sal.empty else None
    
    # debits between rd and next_sal_date
    if next_sal_date is not None:
        debits_until_sal = user_events[(user_events.settlement_date >= rd) & (user_events.settlement_date < next_sal_date) & (user_events.direction == 'debit')]
        total_debit = debits_until_sal.amount.sum()
    else:
        total_debit = 0
        
    print(f"Sample {r.request_id} ({r.user_id}): rd={r.request_date}, safe_true={safe_true}, req={r.requested_amount}, bal-min={slack:.2f}, next_sal={next_sal_date}, debits_before_sal={total_debit:.2f}, diff={slack - safe_true:.2f}")
