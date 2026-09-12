from pathlib import Path
import pandas as pd

ROOT = Path(r"c:\Users\Arkodeep\Desktop\hackerrank-orchestrate-september26-main\hackerrank-orchestrate-september26-main")
truth = pd.read_csv(ROOT / 'dataset' / 'sample_requests.csv')
profiles = pd.read_csv(ROOT / 'dataset' / 'financial_profiles.csv')
events = pd.read_csv(ROOT / 'dataset' / 'financial_events.csv')
events['settlement_date'] = pd.to_datetime(events['settlement_date'])
messages = pd.read_csv(ROOT / 'dataset' / 'messages.csv')

for u_id, req_id in [('user_05', 'request_05'), ('user_10', 'request_10'), ('user_14', 'request_14'), ('user_15', 'request_15'), ('user_20', 'request_20'), ('user_24', 'request_24'), ('user_25', 'request_25')]:
    row = truth[truth.request_id == req_id].iloc[0]
    prof = profiles[profiles.user_id == u_id].iloc[0]
    rd = pd.Timestamp(row.request_date)
    print(f"\n=================== {req_id} ({u_id}) ===================")
    print(f"rd: {rd.date()}, cur_bal: {prof.current_available_balance}, min_bal: {prof.minimum_balance_to_keep}, bal-min: {prof.current_available_balance - prof.minimum_balance_to_keep:.2f}")
    print(f"safe_true: {row.amount_safe_to_pay}")
    print(f"protect: {prof.expense_categories_to_protect}")
    print(f"reduce: {prof.expense_categories_user_is_willing_to_reduce}, stop: {prof.expense_categories_user_is_willing_to_stop}")
    
    # Check messages
    u_msgs = messages[messages.user_id == u_id]
    if not u_msgs.empty:
        print("Messages:")
        for _, m in u_msgs.iterrows():
            print(f"  {m.sent_at}: {m.message_text}")
            
    # Check events within 90 days after rd
    u_events = events[(events.user_id == u_id) & (events.settlement_date >= rd) & (events.settlement_date <= rd + pd.Timedelta(days=90))].sort_values('settlement_date')
    if not u_events.empty:
        print("Upcoming explicit events:")
        for _, e in u_events.iterrows():
            print(f"  {e.settlement_date.date()} | {e.amount} {e.currency} | {e.direction} | {e.category} | {e.status} | {e.flexibility} | {e.description}")
            
    # Check past settled events around rd
    past_events = events[(events.user_id == u_id) & (events.settlement_date <= rd) & (events.settlement_date >= rd - pd.Timedelta(days=35))].sort_values('settlement_date')
    print("Recent past events:")
    for _, e in past_events.iterrows():
        print(f"  {e.settlement_date.date()} | {e.amount} {e.currency} | {e.direction} | {e.category} | {e.status} | {e.flexibility} | {e.description}")
