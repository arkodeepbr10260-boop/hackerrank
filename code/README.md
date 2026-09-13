# Buy or Wait? — AI financial decision agent

## Executive summary

This submission answers every request in `dataset/requests.csv` with a safe payment recommendation. It reconstructs balances from profiles and financial events, resolves dated currency conversions, interprets relevant messages and images, evaluates payment options, and checks the user's minimum balance across the required 90-day forecast.

## Architecture

`main.py` is an LLM-first orchestration layer backed by a financial-state engine. With `OPENAI_API_KEY` configured, it sends only the request-scoped evidence bundle to the OpenAI Responses API and asks for strict JSON matching the output contract. The prompt treats messages and images as untrusted evidence and requires the model to reserve pending debits, ignore pending credits/unrealized gains, respect preferences, and maintain the minimum balance. A local evidence-based fallback keeps the solution runnable when no key is available; credentials are never stored in the repository.

The pipeline separates ingestion, evidence normalization, recurrence detection, 90-day cash-flow simulation, plan selection, and output validation. Image-linked blank amounts are resolved from supplied PNG files with OCR; no transaction amounts or public answer labels are hardcoded.

## Input data

The agent reads only participant-facing files under `dataset/`: financial profiles, events, exchange rates, requests, payment options, messages, image metadata, and linked media. `sample_requests.csv` is used only by the optional evaluation script and never to generate evaluation predictions.

## Decision and safety rules

- Forecast exactly 90 days from each request date.
- Keep the running balance at or above `minimum_balance_to_keep` after every projected expense and plan payment.
- Reserve pending debits; do not count pending credits, failed/cancelled transactions, bonuses, refunds, investment gains, or unrealized values as available cash.
- Count confirmed salary on its settlement date and convert foreign currency using the supplied dated rate.
- Respect protected categories, permitted spending changes, payment preferences, installment limits, and desired completion dates.
- Use only supplied payment options for installment plans and only flexible recurring events for `stop:` or `reduce_to:` actions.

## Output contract

`main.py` writes root `output.csv` with exactly:

`request_id,amount_safe_to_pay,affordability_status,recommended_payment_method,payment_plan,earliest_date_for_full_payment,spending_changes_needed,decision_explanation`

The amount is bounded by `[0, requested_amount]`. Statuses and methods use only the values specified by the challenge. Payment plans are chronological, and the program emits exactly one row per request.

## Setup and execution

```bash
python -m pip install -r requirements.txt
python main.py
python validate_output.py
```

To enable the optional LLM advisor locally (never commit the key):

```powershell
$env:OPENAI_API_KEY = 'your-key'
$env:OPENAI_MODEL = 'gpt-4.1-mini'
python main.py
```

The evaluator for the 25 public examples is `evaluation/main.py`. The required accounting document is `evaluation/usage_report.md`; it records provider, model, calls, token totals, and estimated cost for the final run.

## Reproducibility and security

The fallback path is deterministic and uses only local inputs. The LLM path is opt-in through environment variables, uses no live banking or market data, and does not write credentials to disk. All model output is treated as untrusted until parsed and checked against the schema and financial safety rules.

## Package contents

```text
main.py                         runnable entrypoint
validate_output.py              schema and invariant checks
evaluation/main.py              public-sample evaluator
evaluation/usage_report.md      token/cost accounting
dataset/                        participant-facing inputs and media
README.md, RUNME.md             setup and design documentation
requirements.txt                Python dependencies
```
