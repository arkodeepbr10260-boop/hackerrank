"""Validate the Buy or Wait output contract without external services."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
required = ['request_id','amount_safe_to_pay','affordability_status','recommended_payment_method',
            'payment_plan','earliest_date_for_full_payment','spending_changes_needed','decision_explanation']
allowed_status = {'affordable_now','affordable_with_plan','affordable_later','not_affordable'}
allowed_method = {'full_payment','partial_payment','installments','wait','not_recommended'}

with (ROOT / 'output.csv').open(newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
with (ROOT / 'dataset' / 'requests.csv').open(newline='', encoding='utf-8') as f:
    requests = list(csv.DictReader(f))

assert rows and rows[0].keys() == set(required), 'output schema mismatch'
assert len(rows) == len(requests), f'expected {len(requests)} rows, got {len(rows)}'
assert {r['request_id'] for r in rows} == {r['request_id'] for r in requests}, 'request IDs mismatch'
request_by_id = {q['request_id']: q for q in requests}
issues = []
for r in rows:
    q = request_by_id.get(r['request_id'])
    if q is None:
        issues.append(f"{r['request_id']}: unknown request")
        continue
    try:
        safe, requested = float(r['amount_safe_to_pay']), float(q['requested_amount'])
        if not 0 <= safe <= requested: issues.append(f"{r['request_id']}: amount out of bounds")
    except ValueError:
        issues.append(f"{r['request_id']}: invalid amount")
    if r['affordability_status'] not in allowed_status: issues.append(f"{r['request_id']}: invalid status")
    if r['recommended_payment_method'] not in allowed_method: issues.append(f"{r['request_id']}: invalid method")
if issues:
    raise SystemExit('\n'.join(issues[:20]))
print(f'VALID: {len(rows)} rows, schema and invariants passed')
