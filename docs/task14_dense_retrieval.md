# Task 14 · Dense evidence retrieval baseline

The experiment compares exact cosine ranking of MiniLM embeddings against BM25
on the eight Task 07 development cases. It uses the same five curated claims
and the same case and document fields for both arms. One document corresponds
to one Claim ID. Unknown case fields are omitted and explicit false values
are preserved. Ties fall back to Claim ID order. Only ranking is evaluated.

MiniLM runs locally using the upstream FP32 ONNX export. Its output is
attention-mask-weighted mean pooled and L2-normalized. The implementation
verifies both model file digests before inference and records the model
revision, runtime versions, token budget, case-fixture hash and evidence
snapshot hashes. [MiniLM model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)

## Setup and rerun

The run was verified with Python 3.12 and ONNX Runtime on Linux CPU. Use the
two local curated OncoKG JSON files in `data/curated/`. Install the optional
dependencies and fetch the pinned model files once, from repository root:

```bash
python -m pip install -r requirements-dense.txt
revision=1110a243fdf4706b3f48f1d95db1a4f5529b4d41
model_dir=data/raw/minilm-task14
base="https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/$revision"
mkdir -p "$model_dir/onnx"
curl -fL "$base/tokenizer.json" -o "$model_dir/tokenizer.json"
curl -fL "$base/onnx/model.onnx" -o "$model_dir/onnx/model.onnx"
python codes/demo/task14_dense_retrieval.py pilot --model-dir "$model_dir" \
  --k 3 --output docs/results/task14-dense-pilot.json
```

Ranking and scoring run offline after model setup. Choose a fresh output
filename for reruns. The BM25 export can also run without model files or
the optional dense dependencies.

## Observed development result

| Method | Precision@3 | Recall@3 | MRR |
| --- | ---: | ---: | ---: |
| Lexical BM25 | 20.8% | 73.3% | 0.750 |
| Dense MiniLM | 20.8% | 73.3% | 0.740 |

Precision is averaged across all eight cases. Recall and MRR are averaged
across the five cases with a reference match. MRR uses the complete ranking.
The dense arm reached its 256-token model limit on two of the five claim
documents, the AURA3 record (286 tokens before truncation) and the Pao record
(258 tokens). All eight case texts fit. BM25 used the complete text fields,
so token budget remains one practical difference between arms.

The two methods yielded equal top-three metrics on the development set.
MiniLM had slightly lower MRR. The developer-authored labels, small corpus,
and input truncation limit interpretation. The Task 11 cases were held back
for independent review. This run does not measure a retrieved context's
effect on language-model generation.

## Task 13 prediction export

After the reference is frozen, give the ranker a case-only JSON file with
a `cases` array and the SHA-256 digest of the reference. Keep the reference's
labels with the evaluator. Dense rank export:

```bash
reference_sha=$(shasum -a 256 /path/to/frozen-reference.json | cut -d' ' -f1)
python codes/demo/task14_dense_retrieval.py rank --model-dir "$model_dir" \
  --cases /path/to/case-only.json \
  --reference-sha256 "$reference_sha" \
  --output docs/results/task14-dense-rank.json
```

Use `--method lexical_bm25` for the lexical comparison. Feed each rank list
to the [Task 13 scorer](task13_evaluation.md) at the same k.
