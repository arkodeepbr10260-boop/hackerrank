# Buy or Wait? — V3

Deterministic Python solution for the HackerRank Buy or Wait? challenge.

## V3 changes
- Broader high-frequency variable-expense detection using a longer history window.
- Adds a conservative one-cycle buffer for recurring variable categories that are not explicitly protected but are not explicitly marked stoppable.
- Keeps pending-credit exclusion, confirmed-message handling, dated currency conversion, payment-option validation, and 90-day balance simulation.
- Does not read sample ground-truth labels to generate evaluation predictions.

## Run
From the repository root:

```text
python code/main.py
```

This writes `output.csv` in the repository root.
