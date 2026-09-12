from pathlib import Path
import re
from itertools import combinations
import pandas as pd
import numpy as np

ROOT = Path(r"c:\Users\Arkodeep\Desktop\hackerrank-orchestrate-september26-main\hackerrank-orchestrate-september26-main")
DATA = ROOT / "dataset"
HORIZON_DAYS = 90

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

def split_pipe(x):
    if pd.isna(x) or str(x).strip() == '': return set()
    return {s.strip() for s in str(x).split('|') if s.strip()}

def money(x):
    x = float(x)
    if abs(x - round(x)) < 1e-9: return str(int(round(x)))
    return f"{x:.2f}"

def fmt_date(x):
    return pd.Timestamp(x).strftime('%Y-%m-%d')

print("Definitions loaded.")
