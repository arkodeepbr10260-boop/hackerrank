# Buy or Wait? — LLM financial decision agent

This submission reconstructs each user's financial position from participant-facing CSV and image evidence, then produces one safe payment recommendation per request. It never reads public sample labels to generate evaluation predictions.

## Architecture

`main.py` is an LLM-first agent. When `OPENAI_API_KEY` is present it sends a user-scoped evidence bundle to the OpenAI Responses API and requests strict JSON output. The prompt enforces conservative financial reasoning, the 90-day safety check, minimum-balance protection, dated exchange rates, pending-debit reservation, and payment-option validation. If the API is unavailable, the local evidence engine remains a reproducible offline fallback so the package is runnable without credentials.

## Setup and run

```bash
python -m pip install -r requirements.txt
# PowerShell: $env:OPENAI_API_KEY='...'
# Optional model: $env:OPENAI_MODEL='gpt-4.1-mini'
python main.py
```

The program reads `dataset/` and writes `output.csv` with the required eight columns: `request_id`, `amount_safe_to_pay`, `affordability_status`, `recommended_payment_method`, `payment_plan`, `earliest_date_for_full_payment`, `spending_changes_needed`, and `decision_explanation`.

## Safety and contract

- Forecasts the next 90 days and never permits the balance below `minimum_balance_to_keep`.
- Reserves pending debits; excludes pending credits, failed/cancelled events, unrealized investments, and duplicate transfers.
- Counts confirmed salary only on its settlement date and uses supplied dated exchange rates.
- Respects protected categories, adjustable-category permissions, payment preferences, installment limits, and requested completion dates.
- Uses only flexible recurring expenses for `stop:` or `reduce_to:` actions.
- Produces one row for every request and keeps `amount_safe_to_pay` within `[0, requested_amount]`.

## Evaluation and accounting

Run `python evaluation/main.py` to compare against the 25 public examples. `evaluation/usage_report.md` records provider, model, calls, token totals, and estimated cost for the full run. Keep API keys in environment variables and never commit credentials.
