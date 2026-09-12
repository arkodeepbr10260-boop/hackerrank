# Buy or Wait? - V2 solution

This submission is a deterministic Python financial-planning engine.

## Run

From the repository root:

```bash
python code/main.py
```

The program reads the supplied files from `dataset/` and writes the final predictions to the repository-root `output.csv`.

## V2 improvements

- Reconciles relevant payroll and financial messages, including confirmed salary updates, revised payroll dates, final/ended income, unapproved commissions, and explicit rent changes.
- Extracts missing event amounts from linked PNG images when local OCR is available; blank amounts are never treated as zero.
- Separates explicit future cashflows from historical recurrence inference.
- Forecasts recurring fixed expenses from stable exact-description cadence and smooths protected high-frequency variable spending instead of treating every transaction as a recurrence.
- Treats pending credits, failed/cancelled events, and unrealized investment value conservatively.
- Supports full payment, partial payment, wait, and exact supplied installment schedules.
- Verifies the minimum-balance constraint over the 90-day forecast before accepting a plan.

## Requirements

```bash
python -m pip install -r code/requirements.txt
```

No API keys or external services are required.
