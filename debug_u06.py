from test_engine_v6 import *
eng = Engine(DATA)
truth = pd.read_csv(DATA / 'sample_requests.csv')
r6 = truth.iloc[5]
p6 = eng.profiles[eng.profiles.user_id == r6.user_id].iloc[0]
rd = pd.Timestamp(r6.request_date)
flows = eng.base_cashflows(p6, rd)
print(f"r6 rd={rd.date()}, cur_bal={p6.current_available_balance}, minbal={p6.minimum_balance_to_keep}")
cur = p6.current_available_balance
for f in flows:
    cur += f['delta']
    print(f"   {f['date'].date()} | delta={f['delta']:.2f} | cat={f['category']} | source={f['source']} | bal={cur:.2f}")
