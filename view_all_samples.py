from pathlib import Path
import sys, pandas as pd, numpy as np

ROOT = Path(r"c:\Users\Arkodeep\Desktop\hackerrank-orchestrate-september26-main\hackerrank-orchestrate-september26-main")
truth = pd.read_csv(ROOT / 'dataset' / 'sample_requests.csv')

# Let's see all sample_requests details
for _, r in truth.iterrows():
    print(f"{r.request_id}: req={r.requested_amount}, safe_true={r.amount_safe_to_pay}, status_true={r.affordability_status}, method_true={r.recommended_payment_method}, earliest_true={r.earliest_date_for_full_payment}")
