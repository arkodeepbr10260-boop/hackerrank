from pathlib import Path
import sys, pandas as pd
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'code'))
from main import Engine

eng=Engine(ROOT/'dataset')
truth=pd.read_csv(ROOT/'dataset'/'sample_requests.csv')
preds=[]
for _,r in truth.iloc[:,:8].iterrows(): preds.append(eng.solve(r))
cols=['request_id','amount_safe_to_pay','affordability_status','recommended_payment_method','payment_plan','earliest_date_for_full_payment','spending_changes_needed','decision_explanation']
p=pd.DataFrame(preds,columns=cols)
m=truth.merge(p,on='request_id',suffixes=('_true','_pred'))
for c in cols[1:7]:
    if c=='amount_safe_to_pay':
        mae=(m[c+'_true']-m[c+'_pred']).abs().mean(); print(c,'MAE',round(mae,2))
    else:
        a=m[c+'_true'].fillna('').astype(str); b=m[c+'_pred'].fillna('').astype(str)
        print(c,'accuracy',round((a==b).mean(),3))
print('\nPreview:')
print(m[['request_id','affordability_status_true','affordability_status_pred','recommended_payment_method_true','recommended_payment_method_pred','amount_safe_to_pay_true','amount_safe_to_pay_pred']].to_string(index=False))
