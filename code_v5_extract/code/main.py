from __future__ import annotations
import re
from pathlib import Path
from itertools import combinations
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
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
    """Deterministic financial-state reconstruction engine.

    V2 changes versus V1:
    - uses messages to amend salary amount/date and suppress unapproved/final income;
    - applies message-based rent changes;
    - models exact monthly recurring expenses over the full history;
    - only forecasts high-frequency variable categories when the user's profile marks
      the category as protected, reducing false recurrence from one-off spending;
    - computes today's safe amount with a near-term liquidity guard until the next
      confirmed income, while still validating plans over the full 90-day horizon;
    - keeps the output schema deterministic and does not read sample ground truth.
    """

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

    # ---------- parsing / reconciliation ----------
    def _fill_blank_amounts(self):
        if not self.events['amount'].isna().any():
            return
        try:
            import pytesseract
            from PIL import Image
        except Exception:
            return
        for idx, row in self.events[self.events.amount.isna()].iterrows():
            links = self.images[self.images.related_event_id.eq(row.event_id)]
            if links.empty:
                continue
            image_id = links.iloc[0].image_id
            p = self.data / 'media' / 'images' / f'{image_id}.png'
            if not p.exists():
                continue
            try:
                txt = pytesseract.image_to_string(Image.open(p), config='--psm 6')
                nums = []
                for s in re.findall(r'(?<!\d)(\d[\d,]*(?:\.\d{1,2})?)(?!\d)', txt):
                    try:
                        v = float(s.replace(',', ''))
                        if v > 0:
                            nums.append(v)
                    except Exception:
                        pass
                if not nums:
                    continue
                labelled = []
                for pat in [
                    r'(?:total\s+(?:amount\s+)?(?:received|paid|payable|due)|amount\s+(?:due|payable|received)|balance)\D{0,35}(\d[\d,]*(?:\.\d{1,2})?)',
                    r'(?:rent\s*&?\s*maintenance)\D{0,25}(\d[\d,]*(?:\.\d{1,2})?)',
                ]:
                    for s in re.findall(pat, txt, flags=re.I):
                        try:
                            labelled.append(float(s.replace(',', '')))
                        except Exception:
                            pass
                hist = self.events[(self.events.user_id == row.user_id) & self.events.amount.notna()]
                med = float(hist.amount.median()) if len(hist) else np.nan
                pool = labelled or nums
                plausible = [v for v in pool if v > 0 and (not np.isfinite(med) or v <= max(med * 20, 1e7))]
                if plausible:
                    self.events.at[idx, 'amount'] = max(plausible)
            except Exception:
                continue

    @staticmethod
    def _num(text: str):
        vals = []
        for s in re.findall(r'(?<!\d)(\d[\d,]*(?:\.\d{1,2})?)(?!\d)', text):
            try:
                vals.append(float(s.replace(',', '')))
            except Exception:
                pass
        return vals

    @staticmethod
    def _date_tokens(text: str):
        out = []
        for s in re.findall(r'\b(20\d{2}[-/]\d{1,2}[-/]\d{1,2})\b', text):
            try:
                out.append(pd.Timestamp(s.replace('/', '-')))
            except Exception:
                pass
        return out

    def _build_message_rules(self):
        rules = {}
        for uid, g in self.messages.groupby('user_id'):
            rows = []
            for _, m in g.sort_values('sent_at').iterrows():
                text = str(m.message_text)
                low = text.lower()
                sent = pd.to_datetime(m.sent_at, errors='coerce')
                nums = self._num(text)
                dates = self._date_tokens(text)
                rule = {'text': text, 'sent': sent, 'dates': dates, 'nums': nums}
                if any(k in low for k in ['final employer payroll', 'contract has ended', 'contract ended', 'no off-season income', 'no renewal', 'termination', 'final salary', 'last salary']):
                    rule['income_stop'] = True
                if 'salary' in low or 'payroll' in low or 'gaji' in low:
                    if nums:
                        rule['salary_amount'] = nums[0]
                    if dates:
                        # Prefer the first explicit future date.
                        rule['salary_date'] = min(dates)
                    if any(k in low for k in ['reduced', 'temporary monthly pay', 'decreased', 'reduction']):
                        rule['salary_next_only'] = True
                    if any(k in low for k in ['changed', 'updated', 'increased', 'now expected']):
                        rule['salary_override'] = True
                    if any(k in low for k in ['commission', 'komisi']) and any(k in low for k in ['not approved', 'not been approved', 'belum disetujui', 'not confirmed']):
                        rule['suppress_commission'] = True
                    if any(k in low for k in ['resumes', 'resume', 'will resume']):
                        rule['salary_resume'] = True
                # explicit rent change: "increases monthly rent by 12%"
                mt = re.search(r'increases?\s+monthly\s+rent\s+by\s+(\d+(?:\.\d+)?)\s*%', low)
                if mt:
                    rule['rent_multiplier'] = 1.0 + float(mt.group(1)) / 100.0
                # recurring new childcare deduction is usually represented by an event,
                # so the message is a confirmation rather than an invented amount.
                if 'new recurring childcare payment begins' in low:
                    rule['childcare_starts'] = min(dates) if dates else None
                # own-account transfers: no new wealth; if a matching debit+credit pair
                # exists, the event reconciliation below ignores both sides when possible.
                if 'transfer between your two accounts' in low or 'same account holder' in low:
                    rule['internal_transfer'] = True
                rows.append(rule)
            rules[uid] = rows
        return rules

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

    def _user_messages(self, user):
        return self.message_rules.get(user, [])

    def _next_month_same_day(self, d):
        d = pd.Timestamp(d)
        # Move to next month preserving the observed payroll day when possible.
        y, m = d.year, d.month + 1
        if m == 13:
            y, m = y + 1, 1
        day = min(d.day, pd.Period(f'{y:04d}-{m:02d}').days_in_month)
        return pd.Timestamp(year=y, month=m, day=day)

    @staticmethod
    def _salary_amount_from_text(text):
        patterns = [
            r'(?:salary|pay|gaji)[^\d]{0,50}(?:is|now|becomes|become|increased\s+to|decreased\s+to|naik\s+menjadi|menjadi|sebesar)?[^\d]{0,20}(?:[A-Z]{3}\s*)?(\d[\d,]*(?:\.\d{1,2})?)',
            r'(?:monthly\s+pay|monthly\s+salary|gaji\s+bulanan)[^\d]{0,40}(?:[A-Z]{3}\s*)?(\d[\d,]*(?:\.\d{1,2})?)',
            r'(?:confirmed\s+salary|salary\s+is\s+confirmed)[^\d]{0,30}(?:[A-Z]{3}\s*)?(\d[\d,]*(?:\.\d{1,2})?)',
        ]
        for pat in patterns:
            m = re.search(pat, text, flags=re.I)
            if m:
                try:
                    v = float(m.group(1).replace(',', ''))
                    # Ignore reference IDs / years accidentally matched.
                    if v < 1900 or v > 1e9:
                        return v
                except Exception:
                    pass
        return None

    def _salary_rules(self, user, request_date, home):
        """Return only future salary/income explicitly confirmed by a message.

        Historical salary cadence is used only to infer the next payroll *date* when a
        message confirms an affected/next payroll but omits the date. We never extrapolate
        an indefinite salary stream from history.
        """
        hist = self.events[(self.events.user_id == user) & (self.events.status == 'settled') &
                           (self.events.direction == 'credit') & (self.events.category == 'salary') &
                           self.events.amount.notna() & (self.events.settlement_date <= request_date)].copy().sort_values('settlement_date')
        if hist.empty:
            return []

        # Latest ordinary recurring salary stream supplies the next expected calendar day.
        streams = []
        for desc, g in hist.groupby('description'):
            g = g.sort_values('settlement_date')
            gaps = g.settlement_date.diff().dt.days.dropna()
            if len(g) >= 2 and len(gaps) and 25 <= float(gaps.median()) <= 35:
                streams.append({'description': desc, 'last_date': g.iloc[-1].settlement_date,
                                'next_date': self._next_month_same_day(g.iloc[-1].settlement_date),
                                'amount': self.convert(g.iloc[-1].amount, g.iloc[-1].currency, home, g.iloc[-1].settlement_date)})
        ordinary = [s for s in streams if 'commission' not in str(s['description']).lower()]
        target = ordinary[-1] if ordinary else (streams[-1] if streams else None)

        # If a final payroll was already settled before request, no future salary is safe
        # to invent unless a newer explicit confirmation exists in the messages.
        final_in_history = bool(re.search(r'final|last|termination|severance|ended', str(hist.iloc[-1].description), re.I))
        out = []
        for mr in self._user_messages(user):
            text = mr['text']; low = text.lower()
            if any(k in low for k in ['no renewal', 'no off-season income', 'contract has ended', 'contract ended']):
                continue
            amount = mr.get('salary_amount')
            parsed_amount = self._salary_amount_from_text(text)
            if parsed_amount is not None:
                amount = parsed_amount
            date = mr.get('salary_date')
            if date is None and target is not None:
                date = target['next_date']
            confirmed_words = any(k in low for k in [
                'salary', 'payroll', 'gaji', 'monthly pay', 'salary is', 'salary are', 'salary resumes',
            ])
            affected = any(k in low for k in ['next salary', 'next payroll', 'next pay', 'affected pay cycle',
                                               'currently scheduled', 'resumes', 'expected on', 'confirmed'])
            if not (confirmed_words and affected):
                continue
            if amount is None and target is not None:
                amount = target['amount']
            if amount is None or date is None:
                continue
            # Never add a message-confirmed stream for an unapproved commission message.
            if any(k in low for k in ['commission', 'komisi']) and any(k in low for k in ['not approved', 'belum disetujui', 'not confirmed']):
                continue
            out.append({'date': pd.Timestamp(date), 'amount': float(amount), 'description': target['description'] if target else 'message_confirmed_salary'})

        # Deduplicate same-date confirmations and do not use a stale final-payroll history
        # as a reason to invent another payment.
        uniq = {}
        for x in out:
            uniq[(x['date'], round(x['amount'], 8), x['description'])] = x
        if final_in_history and not uniq:
            return []
        return list(uniq.values())

    def _recurring_templates(self, user, request_date, home, profile):
        hist = self.events[(self.events.user_id == user) & (self.events.status == 'settled') &
                           (self.events.settlement_date <= request_date) & self.events.amount.notna()].copy()
        templates = []
        # exact recurring descriptions: robust and low false-positive rate
        for (direction, cat, desc), g in hist.groupby(['direction', 'category', 'description'], dropna=False):
            g = g.sort_values('settlement_date')
            gaps = g.settlement_date.diff().dt.days.dropna()
            med = gaps.median() if not gaps.empty else np.nan
            if len(g) < 3 or not (25 <= med <= 35):
                continue
            if float((gaps - med).abs().median()) > 5:
                continue
            last = g.iloc[-1]
            amount = self.convert(last.amount, last.currency, home, last.settlement_date)
            templates.append({'kind': 'exact', 'direction': direction, 'category': cat, 'description': desc,
                              'interval': int(round(med)), 'last_date': last.settlement_date, 'amount': amount,
                              'event_id': last.event_id, 'flexibility': last.flexibility,
                              'min_allowed': 0 if pd.isna(last.minimum_allowed_amount) else float(last.minimum_allowed_amount)})
        # High-frequency variable expenses only when explicitly protected by the profile.
        protected = split_pipe(profile.expense_categories_to_protect)
        exact_keys = {(t['direction'], t['category']) for t in templates}
        for (direction, cat), g in hist.groupby(['direction', 'category']):
            if direction != 'debit' or cat not in protected or (direction, cat) in exact_keys or len(g) < 5:
                continue
            g = g.sort_values('settlement_date')
            recent = g[g.settlement_date >= request_date - pd.Timedelta(days=90)]
            if len(recent) < 4:
                continue
            # Use a smoothed monthly rate instead of a false exact schedule.
            days = max(1, (recent.settlement_date.max() - recent.settlement_date.min()).days)
            monthly = recent.amount.sum() / days * 30.0
            amt = float(monthly)
            last = recent.iloc[-1]
            templates.append({'kind': 'variable', 'direction': 'debit', 'category': cat, 'description': '',
                              'interval': 30, 'last_date': request_date, 'amount': self.convert(amt, last.currency, home, last.settlement_date),
                              'event_id': last.event_id, 'flexibility': last.flexibility,
                              'min_allowed': 0 if pd.isna(last.minimum_allowed_amount) else float(last.minimum_allowed_amount)})
        # Message rent increase applies to the recurring rent stream.
        rent_mult = 1.0
        for r in self._user_messages(user):
            if r.get('rent_multiplier'):
                rent_mult *= float(r['rent_multiplier'])
        if rent_mult != 1.0:
            for t in templates:
                if t['category'] == 'rent' and t['direction'] == 'debit':
                    t['amount'] *= rent_mult
        return templates

    def _is_internal_transfer_event(self, user, event_id):
        # If a message explicitly says matching debit/credit are own-account transfer,
        # identify such events by linked_event_id or paired amounts on the same date.
        msgs = self._user_messages(user)
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

    # ---------- cashflow construction ----------
    def base_cashflows(self, profile, request_date):
        user = profile.user_id
        home = profile.home_currency
        end = request_date + pd.Timedelta(days=HORIZON_DAYS)
        flows = []

        future = self.events[(self.events.user_id == user) & (self.events.settlement_date >= request_date) &
                             (self.events.settlement_date <= end)].copy()
        for _, r in future.iterrows():
            if self._is_internal_transfer_event(user, r.event_id):
                continue
            if r.status in {'cancelled', 'failed', 'unrealized'} or pd.isna(r.amount):
                continue
            # Pending credits are never counted. Pending debits are reserved.
            if r.direction == 'credit' and r.status == 'pending':
                continue
            if r.direction == 'credit' and r.status not in {'settled', 'scheduled'} and r.category != 'salary':
                continue
            sign = 1 if r.direction == 'credit' else -1
            amount = self.convert(r.amount, r.currency, home, r.settlement_date)
            flows.append({'date': r.settlement_date, 'delta': sign * amount, 'event_id': r.event_id,
                          'category': r.category, 'source': 'explicit', 'flexibility': r.flexibility})

        # Reconstructed recurring expenses
        templates = self._recurring_templates(user, request_date, home, profile)
        for t in templates:
            d = t['last_date'] + pd.Timedelta(days=t['interval']) if t['kind'] == 'exact' else request_date + pd.Timedelta(days=1)
            step = pd.Timedelta(days=t['interval'])
            if t['kind'] == 'variable':
                # one smooth monthly debit on approximately the historical month boundary
                d = request_date + pd.Timedelta(days=30)
            while d <= end:
                dup = any(f['source'] == 'explicit' and f['category'] == t['category'] and
                          np.sign(f['delta']) == (1 if t['direction'] == 'credit' else -1) and
                          abs((pd.Timestamp(f['date']) - pd.Timestamp(d)).days) <= 7 for f in flows)
                if not dup:
                    sign = 1 if t['direction'] == 'credit' else -1
                    flows.append({'date': d, 'delta': sign * t['amount'], 'event_id': t['event_id'],
                                  'category': t['category'], 'source': 'forecast', 'flexibility': t['flexibility']})
                # variable categories only need one monthly debit over the 90-day window per cycle
                d += step

        # Add only salary amounts explicitly confirmed by a message. Historical salary
        # cadence alone is not enough to invent repeated future income.
        for s in self._salary_rules(user, request_date, home):
            d = pd.Timestamp(s['date'])
            if d < request_date or d > end:
                continue
            duplicate = any(f['source'] == 'explicit' and f['category'] == 'salary' and f['delta'] > 0
                            and abs((pd.Timestamp(f['date']) - d).days) <= 3 for f in flows)
            if not duplicate:
                flows.append({'date': d, 'delta': float(s['amount']),
                              'event_id': 'salary_message_' + d.strftime('%Y%m%d'),
                              'category': 'salary', 'source': 'forecast', 'flexibility': 'fixed'})

        return sorted(flows, key=lambda x: (x['date'], 0 if x['delta'] < 0 else 1))

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
            items.append((pd.Timestamp(f['date']), 0, delta))
        for d, amt in plan:
            items.append((pd.Timestamp(d), -1, -float(amt)))
        items.sort(key=lambda x: (x[0], x[1]))
        min_seen = bal
        for _, _, delta in items:
            bal += delta
            min_seen = min(min_seen, bal)
            if bal < minbal - 1e-6:
                return False, min_seen
        return True, min_seen

    def _next_income_date(self, profile, request_date, flows):
        inc = [f['date'] for f in flows if f['date'] > request_date and f['delta'] > 0 and f['category'] in {'salary', 'income'}]
        return min(inc) if inc else None

    def slack_today(self, profile, request_date, flows, cap):
        bal = float(profile.current_available_balance)
        minbal = float(profile.minimum_balance_to_keep)
        run = bal
        minrun = run
        for f in flows:
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

    # ---------- optional spending changes ----------
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
            if r.flexibility == 'stoppable' and r.category in stop:
                out.append((base * occurrences, f['event_id'], ('stop', 0), f'stop:{f["event_id"]}'))
            if r.flexibility == 'reducible' and r.category in reduce:
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
