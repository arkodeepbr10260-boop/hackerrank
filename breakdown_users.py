from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(r"c:\Users\Arkodeep\Desktop\hackerrank-orchestrate-september26-main\hackerrank-orchestrate-september26-main")
truth = pd.read_csv(ROOT / "dataset" / "sample_requests.csv")
profiles = pd.read_csv(ROOT / "dataset" / "financial_profiles.csv")
events = pd.read_csv(ROOT / "dataset" / "financial_events.csv")
events['settlement_date'] = pd.to_datetime(events['settlement_date'])
messages = pd.read_csv(ROOT / "dataset" / "messages.csv")

for idx, r in truth.iterrows():
    p = profiles[profiles.user_id == r.user_id].iloc[0]
    rd = pd.Timestamp(r.request_date)
    bal = p.current_available_balance
    minbal = p.minimum_balance_to_keep
    safe_true = r.amount_safe_to_pay
    slack = bal - minbal
    
    # Let's inspect all settled events for user in the 60 days before rd
    ue = events[(events.user_id == r.user_id) & (events.settlement_date <= rd) & (events.status == 'settled')].sort_values('settlement_date')
    
    # Monthly recurring items:
    # Group by category, description
    monthly_items = []
    for (cat, desc, direction), g in ue.groupby(['category', 'description', 'direction']):
        if len(g) >= 2:
            gaps = g.settlement_date.diff().dt.days.dropna()
            if not gaps.empty and 25 <= gaps.median() <= 35:
                last_row = g.iloc[-1]
                monthly_items.append((direction, cat, desc, last_row.settlement_date.day, last_row.amount, last_row.settlement_date))
                
    # Messages
    u_msgs = messages[messages.user_id == r.user_id]
    
    print(f"\n--- {r.request_id} ({r.user_id}) | rd: {rd.date()} | safe_true: {safe_true} | bal-min: {slack:.2f} | diff: {slack - safe_true:.2f} ---")
    print(f"Monthly recurring items found ({len(monthly_items)}):")
    for item in monthly_items:
        print(f"   {item[0]} | {item[1]} | {item[2]} | day={item[3]} | amt={item[4]} | last_date={item[5].date()}")
    if not u_msgs.empty:
        print("Messages:")
        for _, m in u_msgs.iterrows():
            print(f"   {m.message_text[:100]}...")
