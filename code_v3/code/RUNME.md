# Buy or Wait? solution

Run from the repository root:

```bash
pip install -r code/requirements.txt
python3 code/main.py
```

The program reads only participant-facing files under `dataset/` and writes `output.csv` in the repository root.

Optional local OCR uses Tesseract for image-linked transactions with a blank amount. If Tesseract is installed on the machine, `pytesseract` will use it automatically.

To evaluate against the 25 public solved samples:

```bash
python3 code/evaluation/main.py
```
