from test_engine_v6 import *
eng = Engine(DATA)

# Let's inspect all recurring intervals in events.csv across all categories
ue = eng.events[(eng.events.status == 'settled') & eng.events.amount.notna()].copy()
results = []
for (u, cat, desc, direction), g in ue.groupby(['user_id', 'category', 'description', 'direction']):
    if len(g) >= 3:
        g = g.sort_values('settlement_date')
        gaps = g.settlement_date.diff().dt.days.dropna()
        if not gaps.empty:
            med = gaps.median()
            std = gaps.std()
            if std <= 3 and 5 <= med <= 35:
                results.append((u, cat, desc, direction, med, g.iloc[-1].amount, len(g)))

df_res = pd.DataFrame(results, columns=['user', 'cat', 'desc', 'dir', 'median_gap', 'last_amt', 'count'])
print("Recurring items with std <= 3 and 5 <= med <= 35:")
print(df_res.median_gap.value_counts())
print("\nSample of non-monthly recurring items:")
print(df_res[df_res.median_gap < 25].head(20).to_string())
