from pathlib import Path
import pandas as pd

ROOT = Path(r"c:\Users\Arkodeep\Desktop\hackerrank-orchestrate-september26-main\hackerrank-orchestrate-september26-main")
events = pd.read_csv(ROOT / "dataset" / "financial_events.csv")
events['settlement_date'] = pd.to_datetime(events['settlement_date'])
messages = pd.read_csv(ROOT / "dataset" / "messages.csv")
images = pd.read_csv(ROOT / "dataset" / "images.csv")

u6 = events[events.user_id == 'user_06'].sort_values('settlement_date')
print("user_06 events:")
print(u6[['event_id', 'settlement_date', 'amount', 'currency', 'direction', 'category', 'status', 'description']].to_string())

print("\nuser_06 messages:")
print(messages[messages.user_id == 'user_06'])
