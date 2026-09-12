from test_engine_v6 import *
eng = Engine(DATA)
truth = pd.read_csv(DATA / 'sample_requests.csv')
r1 = truth.iloc[0]
p1 = eng.profiles[eng.profiles.user_id == r1.user_id].iloc[0]
rd = pd.Timestamp(r1.request_date)
flows = eng.base_cashflows(p1, rd)
print('cur_bal:', p1.current_available_balance, 'minbal:', p1.minimum_balance_to_keep)
cur = p1.current_available_balance
for f in flows:
    cur += f['delta']
    print(f"{f['date'].date()} | {f['delta']:.2f} | {f['category']} | {f['source']} | bal={cur:.2f}")
