# Task 20 · Reproducible report demonstration

The demonstration archive opens without Python. It contains
`case-comparison.md` for the side-by-side BM25 and graph example,
`reports.json` for all 56 development reports at the default cutoff, and
`manifest.json` for the case, cutoff and SHA-256 fingerprints of the inputs
and outputs.

Run from the repository root with the saved Task 15 rankings and the two
local curated evidence inputs. The standard library is sufficient for this
step. Neo4j and the embedding model are needed upstream to reproduce Task 15.

```bash
python codes/demo/task20_demo_bundle.py build \
  --rankings docs/results/task15-retrieval-comparison.json \
  --bundle docs/results/task20-demo.zip

python codes/demo/task20_demo_bundle.py verify \
  --rankings docs/results/task15-retrieval-comparison.json \
  --bundle docs/results/task20-demo.zip
```

Build validates the new bundle before publishing it to a fresh path. Use
`--case-id` to change the illustrated development case or `--k` to change the
cutoff. Verify checks archive membership, replays the report and case view, and
checks their bytes against the rebuilt manifest. Hashes identify the supplied
snapshots. They do not establish input authenticity or an independent
evaluation. No real patient data or external model calls are part of this demo.
