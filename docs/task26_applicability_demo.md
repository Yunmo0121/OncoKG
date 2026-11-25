# Task 26 · Offline presentation bundle

Open `comparison.md` first. It explains the five synthetic scenarios in
Chinese and walks through two cases using the same study. One case needs
a sourced eligibility limit. The other keeps its review source because the
eligibility note applies to a different analysis population.

`reports.json` includes the synthetic inputs, initial rankings, selection
decisions, and 15 complete report outputs. `manifest.json` records the
three-row limit, report count, and file hashes. The examples use
placeholder URLs and a manually defined engineering reference.

Run from the repository root using Python alone. Choose a fresh bundle path
when building.

```bash
python codes/demo/task26_applicability_demo.py build --bundle docs/results/OncoKG-Task26-Demo.zip
python codes/demo/task26_applicability_demo.py verify --bundle docs/results/OncoKG-Task26-Demo.zip
PYTHONPATH=codes/demo python -m unittest test_task26_applicability_demo -v
```

Verification replays the cases and checks the exact bytes of all three
files. The archive contains no graph database, curated evidence snapshot,
credentials, or patient records.
