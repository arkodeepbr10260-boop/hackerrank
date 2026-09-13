from __future__ import annotations
import re
from pathlib import Path
from itertools import combinations
import pandas as pd
import numpy as np

# Resolve correctly whether this file is run from code/ or the archive root.
HERE = Path(__file__).resolve().parent
ROOT = HERE if (HERE / 'dataset').exists() else HERE.parent
DATA = ROOT / 'dataset'
OUT = ROOT / 'output.csv'
HORIZON_DAYS = 90

def split_pipe(x):
    if pd.isna(x) or str(x).strip() == '':
        return set()
    return {s.strip() for s in str(x).split('|') if s.strip()}

def money(x):
    x = float(x)
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.2f}"

def fmt_date(x):
    return pd.Timestamp(x).strftime('%Y-%m-%d')


class Engine:
    def __init__(self, data_dir=DATA):
        self.data = Path(data_dir)
        self.profiles = pd.read_csv(self.data / 'financial_profiles.csv')
        self.events = pd.read_csv(self.data / 'financial_events.csv')
        for c in ['event_date', 'settlement_date']:
            self.events[c] = pd.to_datetime(self.events[c], errors='coerce')
        self.rates = pd.read_csv(self.data / 'exchange_rates.csv')
        self.rates['rate_date'] = pd.to_datetime(self.rates['rate_date'], errors='coerce')
        self.options = pd.read_csv(self.data / 'request_payment_options.csv')
        self.options['first_payment_date'] = pd.to_datetime(self.options['first_payment_date'], errors='coerce')
        self.messages = pd.read_csv(self.data / 'messages.csv')
        self.images = pd.read_csv(self.data / 'images.csv')
        self._fill_blank_amounts()
        self.message_rules = self._build_message_rules()

    def _fill_blank_amounts(self):
        if self.events['amount'].isna().any():
            try:
                import pytesseract
                from PIL import Image
                for idx, row in self.events[self.events.amount.isna()].iterrows():
                    links = self.images[self.images.related_event_id.eq(row.event_id)]
                    if links.empty: continue
                    image_id = links.iloc[0].image_id
                    p = self.data / 'media' / 'images' / f'{image_id}.png'
                    if not p.exists(): continue
                    txt = pytesseract.image_to_string(Image.open(p), config='--psm 6')
                    nums = [float(s.replace(',', '')) for s in re.findall(r'(?<!\d)(\d[\d,]*(?:\.\d{1,2})?)(?!\d)', txt) if float(s.replace(',', '')) > 0]
                    if nums: self.events.at[idx, 'amount'] = max(nums)
            except Exception:
                pass

    def convert(self, amount, currency, home, date):
        if pd.isna(amount):
            return 0.0
        amount = float(amount)
        if pd.isna(currency) or currency == home:
            return amount
        d = pd.Timestamp(date)
        x = self.rates[(self.rates.rate_date == d) & (self.rates.from_currency == currency) & (self.rates.to_currency == home)]
        if not x.empty:
            return amount * float(x.iloc[0].rate)
        x = self.rates[(self.rates.rate_date == d) & (self.rates.from_currency == home) & (self.rates.to_currency == currency)]
        if not x.empty and float(x.iloc[0].rate):
            return amount / float(x.iloc[0].rate)
        x = self.rates[(self.rates.rate_date <= d) & (self.rates.from_currency == currency) & (self.rates.to_currency == home)].sort_values('rate_date')
        if not x.empty:
            return amount * float(x.iloc[-1].rate)
        x = self.rates[(self.rates.rate_date <= d) & (self.rates.from_currency == home) & (self.rates.to_currency == currency)].sort_values('rate_date')
        if not x.empty and float(x.iloc[-1].rate):
            return amount / float(x.iloc[-1].rate)
        return amount

    def _build_message_rules(self):
        rules = {}
        for uid, g in self.messages.groupby('user_id'):
            user_rules = []
            for _, m in g.sort_values('sent_at').iterrows():
                text = str(m.message_text)
                low = text.lower()
                rule = {'text': text}
                if any(k in low for k in ['contract has ended', 'contract ended', 'no renewal', 'no off-season income', 'termination', 'final employer payroll']):
                    rule['income_stop'] = True
                if 'salary' in low or 'payroll' in low or 'gaji' in low:
                    nums = [float(s.replace(',', '')) for s in re.findall(r'(?<!\d)(\d[\d,]*(?:\.\d{1,2})?)(?!\d)', text)]
                    valid_nums = [v for v in nums if 100 < v < 1e9 and v not in {2024, 2025, 2026}]
                    if valid_nums:
                        rule['salary_amount'] = valid_nums[0]
                mt = re.search(r'increases?\s+monthly\s+rent\s+by\s+(\d+(?:\.\d+)?)\s*%', low)
                if mt:
                    rule['rent_multiplier'] = 1.0 + float(mt.group(1)) / 100.0
                if 'transfer between your two accounts' in low or 'same account holder' in low:
                    rule['internal_transfer'] = True
                user_rules.append(rule)
            rules[uid] = user_rules
        return rules

    def _is_internal_transfer_event(self, user, event_id):
        msgs = self.message_rules.get(user, [])
        if not any(r.get('internal_transfer') for r in msgs):
            return False
        row = self.events[self.events.event_id.eq(event_id)]
        if row.empty:
            return False
        r = row.iloc[0]
        if pd.notna(r.linked_event_id):
            return True
        peers = self.events[(self.events.user_id == user) &
                            (self.events.settlement_date == r.settlement_date) &
                            self.events.amount.notna() &
                            (self.events.event_id != event_id)]
        for _, p in peers.iterrows():
            if p.direction != r.direction and abs(float(p.amount) - float(r.amount)) < 1e-9:
                return True
        return 'transfer between' in str(r.description).lower()

    def _recurring_templates(self, user, request_date, home, profile):
        ue = self.events[(self.events.user_id == user) & self.events.amount.notna()].copy()
        hist = ue[(ue.status == 'settled') & (ue.settlement_date <= request_date)].copy()
        templates = []
        user_msgs = self.message_rules.get(user, [])
        income_stopped = any(r.get('income_stop') for r in user_msgs)

        # 1. Recurring Debits
        protected = split_pipe(profile.expense_categories_to_protect)
        for (direction, cat, desc), g in hist[hist.direction == 'debit'].groupby(['direction', 'category', 'description'], dropna=False):
            g = g.sort_values('settlement_date')
            if len(g) < 2:
                continue
            gaps = g.settlement_date.diff().dt.days.dropna()
            if gaps.empty:
                continue
            med = float(gaps.median())
            if not (5 <= med <= 35):
                continue
            # For non-monthly variable items (med < 25), only include if category is protected or fixed
            if med < 25 and cat not in protected and g.iloc[-1].flexibility != 'fixed':
                continue
            last = g.iloc[-1]
            if (request_date - last.settlement_date).days > max(65, int(med * 2.5)):
                continue
            amount = self.convert(last.amount, last.currency, home, last.settlement_date)
            kind = 'monthly' if 25 <= med <= 35 else 'interval'
            templates.append({
                'kind': kind,
                'direction': 'debit',
                'category': cat,
                'description': desc,
                'day': last.settlement_date.day,
                'interval': int(round(med)),
                'last_date': last.settlement_date,
                'amount': amount,
                'event_id': last.event_id,
                'flexibility': last.flexibility,
                'min_allowed': 0 if pd.isna(last.minimum_allowed_amount) else float(last.minimum_allowed_amount)
            })

        # High-frequency category expenses (groceries, transport) for protected categories
        used_cats = {t['category'] for t in templates if t['direction'] == 'debit'}
        for (direction, cat), g in hist[hist.direction == 'debit'].groupby(['direction', 'category']):
            if cat in used_cats or cat not in protected or len(g) < 5:
                continue
            g = g.sort_values('settlement_date')
            gaps = g.settlement_date.diff().dt.days.dropna()
            if gaps.empty:
                continue
            med = float(gaps.median())
            if not (4 <= med <= 22):
                continue
            last = g.iloc[-1]
            if (request_date - last.settlement_date).days > max(30, int(med * 2.5)):
                continue
            recent = g.tail(min(8, len(g)))
            amt = float(recent.amount.median())
            templates.append({
                'kind': 'interval',
                'direction': 'debit',
                'category': cat,
                'description': f'{cat}_variable',
                'day': last.settlement_date.day,
                'interval': int(round(med)),
                'last_date': last.settlement_date,
                'amount': self.convert(amt, last.currency, home, last.settlement_date),
                'event_id': last.event_id,
                'flexibility': last.flexibility,
                'min_allowed': 0 if pd.isna(last.minimum_allowed_amount) else float(last.minimum_allowed_amount)
            })

        # Apply rent multiplier from messages
        rent_mult = 1.0
        for r in user_msgs:
            if 'rent_multiplier' in r:
                rent_mult *= r['rent_multiplier']
        if rent_mult != 1.0:
            for t in templates:
                if t['category'] == 'rent' and t['direction'] == 'debit':
                    t['amount'] *= rent_mult

        # 2. Recurring Salary / Income
        if not income_stopped:
            future_sal = ue[(ue.direction == 'credit') & (ue.category == 'salary') &
                            (ue.settlement_date >= request_date) & (ue.status.isin(['scheduled', 'settled']))].sort_values('settlement_date')
            past_sal = hist[(hist.direction == 'credit') & (hist.category == 'salary')].sort_values('settlement_date')

            last_was_final = False
            if not past_sal.empty:
                desc_low = str(past_sal.iloc[-1].description).lower()
                if any(k in desc_low for k in ['final', 'last', 'termination', 'severance', 'ended']):
                    last_was_final = True

            if not last_was_final:
                target_sal = None
                if not future_sal.empty:
                    target_sal = future_sal.iloc[0]
                elif not past_sal.empty:
                    if (request_date - past_sal.iloc[-1].settlement_date).days <= 60:
                        target_sal = past_sal.iloc[-1]

                if target_sal is not None:
                    sal_amount = self.convert(target_sal.amount, target_sal.currency, home, target_sal.settlement_date)
                    for r in user_msgs:
                        if 'salary_amount' in r:
                            sal_amount = float(r['salary_amount'])

                    # Use the MODAL salary day from recurring stream (not the last event which may be one-off)
                    # Only override if last event's day is 10+ days off from modal (strongly suggests one-off payment)
                    sal_day = target_sal.settlement_date.day
                    if len(past_sal) >= 3:
                        # Find the most common day among regular monthly salary payments
                        gaps = past_sal.settlement_date.diff().dt.days.dropna()
                        monthly_mask = (gaps >= 25) & (gaps <= 35)
                        if monthly_mask.sum() >= 2:
                            regular_sal = past_sal[past_sal.index.isin(past_sal.index[1:][monthly_mask])]
                            if not regular_sal.empty:
                                day_counts = regular_sal.settlement_date.dt.day.value_counts()
                                modal_day = int(day_counts.index[0])
                                # Only use modal if last event's day is very different (>= 10 days)
                                if abs(sal_day - modal_day) >= 10:
                                    sal_day = modal_day

                    templates.append({
                        'kind': 'monthly',
                        'direction': 'credit',
                        'category': 'salary',
                        'description': str(target_sal.description),
                        'day': sal_day,
                        'interval': 30,
                        'last_date': target_sal.settlement_date,
                        'amount': sal_amount,
                        'event_id': target_sal.event_id,
                        'flexibility': 'fixed',
                        'min_allowed': 0.0
                    })

        return templates

    def base_cashflows(self, profile, request_date):
        user = profile.user_id
        home = profile.home_currency
        end = request_date + pd.Timedelta(days=HORIZON_DAYS)
        flows = []

        # 1. Explicit future events in events.csv
        future = self.events[(self.events.user_id == user) &
                             (self.events.settlement_date >= request_date) &
                             (self.events.settlement_date <= end)].copy()
        for _, r in future.iterrows():
            if self._is_internal_transfer_event(user, r.event_id):
                continue
            if r.status in {'cancelled', 'failed', 'unrealized'} or pd.isna(r.amount):
                continue
            if r.direction == 'credit' and r.status == 'pending':
                continue
            if r.direction == 'credit' and r.status not in {'settled', 'scheduled'} and r.category != 'salary':
                continue
            sign = 1 if r.direction == 'credit' else -1
            amount = self.convert(r.amount, r.currency, home, r.settlement_date)
            flows.append({
                'date': r.settlement_date,
                'delta': sign * amount,
                'event_id': r.event_id,
                'category': r.category,
                'source': 'explicit',
                'flexibility': r.flexibility
            })

        # 2. Reconstructed recurring items
        templates = self._recurring_templates(user, request_date, home, profile)
        for t in templates:
            sign = 1 if t['direction'] == 'credit' else -1
            if t['kind'] == 'monthly':
                day = t['day']
                cur_y, cur_m = request_date.year, request_date.month
                for add_m in range(4):
                    m = cur_m + add_m
                    y = cur_y + (m - 1) // 12
                    m = ((m - 1) % 12) + 1
                    max_d = pd.Period(f'{y:04d}-{m:02d}').days_in_month
                    event_d = pd.Timestamp(year=y, month=m, day=min(day, max_d))
                    if event_d < request_date or event_d > end:
                        continue
                    dup = any(f['category'] == t['category'] and
                              abs((f['date'] - event_d).days) <= 3 and
                              (1 if f['delta'] > 0 else -1) == sign
                              for f in flows)
                    if not dup:
                        flows.append({
                            'date': event_d,
                            'delta': sign * t['amount'],
                            'event_id': t['event_id'],
                            'category': t['category'],
                            'source': 'forecast',
                            'flexibility': t['flexibility']
                        })
            else:
                # Interval based (weekly, 10-day, etc.)
                step = pd.Timedelta(days=t['interval'])
                event_d = t['last_date'] + step
                while event_d < request_date:
                    event_d += step
                while event_d <= end:
                    dup = any(f['category'] == t['category'] and
                              abs((f['date'] - event_d).days) <= 2 and
                              (1 if f['delta'] > 0 else -1) == sign
                              for f in flows)
                    if not dup:
                        flows.append({
                            'date': event_d,
                            'delta': sign * t['amount'],
                            'event_id': t['event_id'],
                            'category': t['category'],
                            'source': 'forecast',
                            'flexibility': t['flexibility']
                        })
                    event_d += step

        # Sort flows so that on the same day, credits come first (+delta before -delta)
        return sorted(flows, key=lambda x: (x['date'], 0 if x['delta'] > 0 else 1))

    def simulate(self, profile, request_date, flows, plan=None, changes=None):
        bal = float(profile.current_available_balance)
        minbal = float(profile.minimum_balance_to_keep)
        plan = plan or []
        changes = changes or {}
        items = []
        for f in flows:
            delta = f['delta']
            ch = changes.get(f['event_id'])
            if f['source'] == 'forecast' and delta < 0 and ch:
                if ch[0] == 'stop':
                    delta = 0.0
                elif ch[0] == 'reduce_to':
                    delta = -float(ch[1])
            pri = -1 if delta > 0 else 0
            items.append((pd.Timestamp(f['date']), pri, delta))
        for d, amt in plan:
            items.append((pd.Timestamp(d), 1, -float(amt)))
        items.sort(key=lambda x: (x[0], x[1]))
        min_seen = bal
        for _, _, delta in items:
            bal += delta
            min_seen = min(min_seen, bal)
            if bal < minbal - 1e-6:
                return False, min_seen
        return True, min_seen

    def slack_today(self, profile, request_date, flows, cap):
        bal = float(profile.current_available_balance)
        minbal = float(profile.minimum_balance_to_keep)
        run = bal
        minrun = run
        sflows = sorted(flows, key=lambda x: (x['date'], 0 if x['delta'] > 0 else 1))
        for f in sflows:
            run += f['delta']
            minrun = min(minrun, run)
        return round(max(0.0, min(float(cap), minrun - minbal)), 2)

    def earliest_full_date(self, profile, request_date, flows, amount):
        for i in range(HORIZON_DAYS + 1):
            d = request_date + pd.Timedelta(days=i)
            ok, _ = self.simulate(profile, request_date, flows, [(d, amount)])
            if ok:
                return d
        return None

    def spending_candidates(self, profile, request_date, flows):
        reduce = split_pipe(profile.expense_categories_user_is_willing_to_reduce)
        stop = split_pipe(profile.expense_categories_user_is_willing_to_stop)
        hist = self.events[(self.events.user_id == profile.user_id) & (self.events.settlement_date <= request_date) &
                           (self.events.status == 'settled')]
        out = []
        seen = set()
        for f in flows:
            if f['source'] != 'forecast' or f['delta'] >= 0 or f['event_id'] in seen:
                continue
            seen.add(f['event_id'])
            row = hist[hist.event_id.eq(f['event_id'])]
            if row.empty:
                continue
            r = row.iloc[0]
            occurrences = sum(1 for z in flows if z['source'] == 'forecast' and z['event_id'] == f['event_id'] and z['delta'] < 0)
            base = -float(f['delta'])
            if r.flexibility in {'stoppable', 'reducible_or_stoppable'} and r.category in stop:
                out.append((base * occurrences, f['event_id'], ('stop', 0), f'stop:{f["event_id"]}'))
            if r.flexibility in {'reducible', 'reducible_or_stoppable'} and r.category in reduce:
                m = 0.0 if pd.isna(r.minimum_allowed_amount) else float(r.minimum_allowed_amount)
                if m < base:
                    out.append(((base - m) * occurrences, f['event_id'], ('reduce_to', m), f'reduce_to:{f["event_id"]}:{money(m)}'))
        out.sort(reverse=True, key=lambda x: x[0])
        return out

    def safe_with_best_changes(self, profile, request_date, flows, plan):
        cands = self.spending_candidates(profile, request_date, flows)[:12]
        for n in (1, 2, 3):
            best = None
            for combo in combinations(cands, n):
                ids = [x[1] for x in combo]
                if len(set(ids)) < n:
                    continue
                changes = {x[1]: x[2] for x in combo}
                ok, minseen = self.simulate(profile, request_date, flows, plan, changes)
                if ok:
                    saving = sum(x[0] for x in combo)
                    key = (n, saving)
                    if best is None or key < best[0]:
                        best = (key, combo, changes, minseen)
            if best:
                return best[1], best[2], best[3]
        return None, None, None

    def option_plan(self, opt):
        n = int(opt.number_of_payments)
        interval = 0 if pd.isna(opt.payment_frequency_days) else int(opt.payment_frequency_days)
        return [(opt.first_payment_date + pd.Timedelta(days=i * interval), float(opt.payment_amount)) for i in range(n)]

    def solve(self, req):
        profile = self.profiles[self.profiles.user_id == req.user_id].iloc[0]
        rd = pd.Timestamp(req.request_date)
        deadline = pd.Timestamp(req.desired_completion_date)
        amt = float(req.requested_amount)
        flows = self.base_cashflows(profile, rd)

        safe = round(self.slack_today(profile, rd, flows, amt), 2)
        earliest = self.earliest_full_date(profile, rd, flows, amt)
        methods = split_pipe(profile.payment_methods_user_will_consider)
        candidates = []

        if 'full_payment' in methods:
            p = [(rd, amt)]
            ok, minseen = self.simulate(profile, rd, flows, p)
            if ok:
                candidates.append((0, amt, rd, 1, '', 'full_payment', p, 'none', minseen))
            else:
                combo, changes, minseen = self.safe_with_best_changes(profile, rd, flows, p)
                if combo:
                    txt = '|'.join(x[3] for x in combo)
                    candidates.append((1, amt, rd, 1, '', 'full_payment', p, txt, minseen))

        if bool(req.allows_partial_payment) and 'partial_payment' in methods and 0 < safe < amt and earliest is not None and earliest <= deadline:
            p = [(rd, safe), (earliest, round(amt - safe, 2))]
            ok, minseen = self.simulate(profile, rd, flows, p)
            if ok:
                candidates.append((0, amt, rd, 2, '', 'partial_payment', p, 'none', minseen))

        if 'installments' in methods:
            opts = self.options[(self.options.request_id == req.request_id) & (self.options.payment_method == 'installments')].copy()
            for _, o in opts.iterrows():
                n = int(o.number_of_payments)
                if pd.notna(profile.max_installment_months) and n > int(profile.max_installment_months):
                    continue
                p = self.option_plan(o)
                if not p or p[-1][0] > deadline:
                    continue
                ok, minseen = self.simulate(profile, rd, flows, p)
                if ok:
                    candidates.append((0, float(o.total_payable_amount), p[0][0], n, str(o.payment_option_id), 'installments', p, 'none', minseen))
                else:
                    combo, changes, minseen = self.safe_with_best_changes(profile, rd, flows, p)
                    if combo:
                        txt = '|'.join(x[3] for x in combo)
                        candidates.append((1, float(o.total_payable_amount), p[0][0], n, str(o.payment_option_id), 'installments', p, txt, minseen))

        if 'full_payment' in methods and earliest is not None and earliest > rd and earliest <= deadline:
            p = [(earliest, amt)]
            ok, minseen = self.simulate(profile, rd, flows, p)
            if ok:
                candidates.append((0, amt, earliest, 1, 'zzzz', 'wait', p, 'none', minseen))

        if candidates:
            candidates.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[4]))
            c = candidates[0]
            method, plan, changes_txt, minseen = c[5], c[6], c[7], c[8]
            status = 'affordable_now' if method == 'full_payment' and changes_txt == 'none' and abs(safe - amt) < 0.011 else 'affordable_with_plan'
            if method == 'wait':
                status = 'affordable_later'
            plan_txt = '|'.join(f'{fmt_date(d)}:{money(a)}' for d, a in plan)
            cur = profile.home_currency
            if method == 'full_payment':
                prefix = '' if changes_txt == 'none' else 'Adjust flexible spending, then '
                expl = f'{prefix}pay {cur} {money(amt)} today while keeping at least {cur} {money(profile.minimum_balance_to_keep)} available.'
            elif method == 'installments':
                expl = f'Use {len(plan)} installments starting {fmt_date(plan[0][0])}; the plan keeps the {cur} {money(profile.minimum_balance_to_keep)} minimum protected.'
            elif method == 'partial_payment':
                expl = f'Pay {cur} {money(plan[0][1])} today and {cur} {money(plan[1][1])} on {fmt_date(plan[1][0])}, while protecting the minimum balance.'
            else:
                expl = f'Wait until {fmt_date(plan[0][0])}, then pay {cur} {money(amt)} in full so the minimum balance remains protected.'
            return [req.request_id, safe, status, method, plan_txt, fmt_date(earliest) if earliest is not None else '', changes_txt, expl]

        cur = profile.home_currency
        expl = f'Do not proceed by {fmt_date(deadline)}; no eligible plan keeps the {cur} {money(profile.minimum_balance_to_keep)} minimum protected through the 90-day forecast.'
        return [req.request_id, safe, 'not_affordable', 'not_recommended', 'none', fmt_date(earliest) if earliest is not None else '', 'none', expl]


def run(request_file='requests.csv', output_path=OUT):
    eng = Engine(DATA)
    reqs = pd.read_csv(DATA / request_file)
    rows = [eng.solve(r) for _, r in reqs.iterrows()]
    cols = ['request_id', 'amount_safe_to_pay', 'affordability_status', 'recommended_payment_method',
            'payment_plan', 'earliest_date_for_full_payment', 'spending_changes_needed', 'decision_explanation']
    pd.DataFrame(rows, columns=cols).to_csv(output_path, index=False)
    print(f'Wrote {len(rows)} predictions to {output_path}')


if __name__ == '__main__':
    run()
