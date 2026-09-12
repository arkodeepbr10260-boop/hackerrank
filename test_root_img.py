from pathlib import Path
import sys, pandas as pd
ROOT = Path(r"c:\Users\Arkodeep\Desktop\hackerrank-orchestrate-september26-main\hackerrank-orchestrate-september26-main")
sys.path.insert(0, str(ROOT))
import main as root_main

# Set image amounts in root_main
eng = root_main.Engine(ROOT / 'dataset')
from test_acc import IMAGE_AMOUNTS
for eid, amt in IMAGE_AMOUNTS.items():
    eng.events.loc[eng.events.event_id == eid, 'amount'] = amt

truth = pd.read_csv(ROOT / 'dataset' / 'sample_requests.csv')
preds = [eng.solve(r) for _, r in truth.iloc[:, :8].iterrows()]
cols = ['request_id', 'amount_safe_to_pay', 'affordability_status', 'recommended_payment_method',
        'payment_plan', 'earliest_date_for_full_payment', 'spending_changes_needed', 'decision_explanation']
p = pd.DataFrame(preds, columns=cols)
m = truth.merge(p, on='request_id', suffixes=('_true', '_pred'))
for c in cols[1:7]:
    if c == 'amount_safe_to_pay':
        mae = (m[c+'_true'] - m[c+'_pred']).abs().mean()
        acc = (m[c+'_true'].round(2) == m[c+'_pred'].round(2)).mean()
        print(c, 'MAE', round(mae, 2), 'exact match accuracy', round(acc, 3))
    else:
        a = m[c+'_true'].fillna('').astype(str)
        b = m[c+'_pred'].fillna('').astype(str)
        print(c, 'accuracy', round((a == b).mean(), 3))
