from pathlib import Path
import pandas as pd

ROOT = Path(r"c:\Users\Arkodeep\Desktop\hackerrank-orchestrate-september26-main\hackerrank-orchestrate-september26-main")
samples = pd.read_csv(ROOT / "dataset" / "sample_requests.csv")
profiles = pd.read_csv(ROOT / "dataset" / "financial_profiles.csv")
m = samples.merge(profiles, on="user_id")
for _, r in m.iterrows():
    diff_bal = r["current_available_balance"] - r["minimum_balance_to_keep"]
    print(f"{r['request_id']} ({r['user_id']}): req={r['requested_amount']}, cur_bal={r['current_available_balance']}, min_bal={r['minimum_balance_to_keep']}, bal-min={diff_bal:.2f}, safe_true={r['amount_safe_to_pay']}")
