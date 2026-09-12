from pathlib import Path
import sys, pandas as pd

ROOT = Path(r"c:\Users\Arkodeep\Desktop\hackerrank-orchestrate-september26-main\hackerrank-orchestrate-september26-main")
sys.path.insert(0, str(ROOT))
from main import Engine

DATA = ROOT / 'dataset'
eng = Engine(DATA)
truth = pd.read_csv(DATA / 'sample_requests.csv')
preds = [eng.solve(r) for _, r in truth.iloc[:, :8].iterrows()]

cols = ['request_id', 'amount_safe_to_pay', 'affordability_status', 'recommended_payment_method',
        'payment_plan', 'earliest_date_for_full_payment', 'spending_changes_needed']
p = pd.DataFrame(preds, columns=cols + ['decision_explanation'])
m = truth.merge(p, on='request_id', suffixes=('_true', '_pred'))

print("=" * 45)
print("  V8 ENGINE ACCURACY")
print("=" * 45)
for c in cols[1:]:
    if c == 'amount_safe_to_pay':
        exact = (m[c+'_true'].round(2) == m[c+'_pred'].round(2)).mean()
        print(f"  {c:<35} {exact:>5.0%}")
    else:
        a = m[c+'_true'].fillna('').astype(str)
        b = m[c+'_pred'].fillna('').astype(str)
        print(f"  {c:<35} {(a == b).mean():>5.0%}")
print("=" * 45)
