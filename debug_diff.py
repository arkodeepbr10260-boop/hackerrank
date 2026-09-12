from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(r"c:\Users\Arkodeep\Desktop\hackerrank-orchestrate-september26-main\hackerrank-orchestrate-september26-main")
truth = pd.read_csv(ROOT / "dataset" / "sample_requests.csv")
profiles = pd.read_csv(ROOT / "dataset" / "financial_profiles.csv")
events = pd.read_csv(ROOT / "dataset" / "financial_events.csv")
events['settlement_date'] = pd.to_datetime(events['settlement_date'])
events['event_date'] = pd.to_datetime(events['event_date'])
rates = pd.read_csv(ROOT / "dataset" / "exchange_rates.csv")
rates['rate_date'] = pd.to_datetime(rates['rate_date'])

IMAGE_AMOUNTS = {
    'event_253': 4365000.0,
    'event_1442': 100000.0,
    'event_1545': 41272.0,
    'event_1700': 2854.0,
    'event_1786': 704.05,
    'event_3051': 1995.0,
    'event_3231': 8528.0,
    'event_4535': 15339.0,
    'event_5170': 723.0,
    'event_6033': 79679.26,
    'event_6859': 3650.0,
    'event_7307': 33.50,
    'event_7941': 2298.0,
    'event_9421': 4543.0,
    'event_9806': 9968.0,
    'event_10521': 393.22,
}

for eid, amt in IMAGE_AMOUNTS.items():
    events.loc[events.event_id == eid, 'amount'] = amt

def convert(amount, currency, home, date):
    if pd.isna(amount): return 0.0
    amount = float(amount)
    if currency == home or pd.isna(currency): return amount
    d = pd.Timestamp(date)
    exact = rates[(rates.rate_date == d) & (rates.from_currency == currency) & (rates.to_currency == home)]
    if not exact.empty: return amount * float(exact.iloc[0].rate)
    inv = rates[(rates.rate_date == d) & (rates.from_currency == home) & (rates.to_currency == currency)]
    if not inv.empty and float(inv.iloc[0].rate) != 0: return amount / float(inv.iloc[0].rate)
    x = rates[(rates.rate_date <= d) & (rates.from_currency == currency) & (rates.to_currency == home)].sort_values('rate_date')
    if not x.empty: return amount * float(x.iloc[-1].rate)
    x = rates[(rates.rate_date <= d) & (rates.from_currency == home) & (rates.to_currency == currency)].sort_values('rate_date')
    if not x.empty and float(x.iloc[-1].rate) != 0: return amount / float(x.iloc[-1].rate)
    return amount

def next_date_same_day(d, cur_date):
    y, m, day = cur_date.year, cur_date.month, d.day
    # find next month on or after cur_date
    cand = pd.Timestamp(year=y, month=m, day=min(day, pd.Period(f'{y:04d}-{m:02d}').days_in_month))
    if cand < cur_date:
        m += 1
        if m > 12:
            m = 1
            y += 1
        cand = pd.Timestamp(year=y, month=m, day=min(day, pd.Period(f'{y:04d}-{m:02d}').days_in_month))
    return cand

for idx in range(25):
    r = truth.iloc[idx]
    prof = profiles[profiles.user_id == r.user_id].iloc[0]
    rd = pd.Timestamp(r.request_date)
    home = prof.home_currency
    bal = prof.current_available_balance
    minbal = prof.minimum_balance_to_keep
    safe_true = r.amount_safe_to_pay
    
    # Let's test a pure day-by-day cashflow over 90 days
    # 1. explicit future events
    ue = events[(events.user_id == r.user_id) & (events.settlement_date >= rd) & (events.settlement_date <= rd + pd.Timedelta(days=90))].copy()
    
    flows = []
    for _, ev in ue.iterrows():
        if ev.status in {'cancelled', 'failed', 'unrealized'} or pd.isna(ev.amount): continue
        if ev.direction == 'credit' and ev.status == 'pending': continue
        if ev.direction == 'credit' and ev.status not in {'settled', 'scheduled'} and ev.category != 'salary': continue
        sign = 1 if ev.direction == 'credit' else -1
        amt = convert(ev.amount, ev.currency, home, ev.settlement_date)
        flows.append({'date': ev.settlement_date, 'delta': sign * amt, 'cat': ev.category, 'source': 'explicit'})
        
    # 2. recurring monthly items from history (last 120 days)
    hist = events[(events.user_id == r.user_id) & (events.settlement_date <= rd) & (events.status == 'settled')].copy()
    for (direction, cat, desc), g in hist.groupby(['direction', 'category', 'description']):
        if len(g) >= 2:
            gaps = g.settlement_date.diff().dt.days.dropna()
            if not gaps.empty and 25 <= gaps.median() <= 35:
                last_ev = g.iloc[-1]
                day = last_ev.settlement_date.day
                # advance month by month
                cur_y, cur_m = rd.year, rd.month
                for add_m in range(4):
                    m = cur_m + add_m
                    y = cur_y + (m - 1) // 12
                    m = ((m - 1) % 12) + 1
                    max_d = pd.Period(f'{y:04d}-{m:02d}').days_in_month
                    event_d = pd.Timestamp(year=y, month=m, day=min(day, max_d))
                    if event_d < rd or event_d > rd + pd.Timedelta(days=90):
                        continue
                    # check dup with explicit
                    dup = any(f['cat'] == cat and abs((f['date'] - event_d).days) <= 3 and (1 if f['delta'] > 0 else -1) == (1 if direction == 'credit' else -1) for f in flows)
                    if not dup:
                        sign = 1 if direction == 'credit' else -1
                        amt = convert(last_ev.amount, last_ev.currency, home, last_ev.settlement_date)
                        flows.append({'date': event_d, 'delta': sign * amt, 'cat': cat, 'source': 'recurring'})
                        
    # Sort flows
    flows.sort(key=lambda x: (x['date'], 0 if x['delta'] < 0 else 1))
    
    # simulate
    cur = bal
    min_bal_seen = cur
    for f in flows:
        cur += f['delta']
        min_bal_seen = min(min_bal_seen, cur)
        
    safe_pred = max(0.0, min(float(r.requested_amount), min_bal_seen - minbal))
    print(f"{r.request_id} ({r.user_id}): safe_true={safe_true}, safe_pred={safe_pred:.2f}, diff={safe_pred - safe_true:.2f}")
