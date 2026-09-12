from pathlib import Path
import sys, pandas as pd

ROOT = Path(r"c:\Users\Arkodeep\Desktop\hackerrank-orchestrate-september26-main\hackerrank-orchestrate-september26-main")
truth = pd.read_csv(ROOT / 'dataset' / 'sample_requests.csv')
for idx in range(len(truth)):
    r = truth.iloc[idx]
    print(f"{r.request_id} ({r.user_id}): safe={r.amount_safe_to_pay}, req={r.requested_amount}, status={r.affordability_status}, method={r.recommended_payment_method}, changes={r.spending_changes_needed}, earliest={r.earliest_date_for_full_payment}")
    print(f"   Explanation: {r.decision_explanation}")
