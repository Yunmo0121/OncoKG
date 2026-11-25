"""Run an offline dense evidence retriever and compare it with BM25."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from benchmark_task07 import sha256_file
from condition_retrieval import ALLOWED_CLAIMS, load_sources, validate_case
from task07_retrieval_pilot import (
    PILOT, REFERENCE, bm25_scores, case_query_fields, claim_text_fields,
    rank_claims, read_cases, score_ranking, summarize_rankings, tokens,
)
from task11_review_pack import CASE_FIELDS
from task13_evaluation import write_json

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
MODEL_SHA256 = {
    "tokenizer.json": "be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037",
    "onnx/model.onnx": "6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452",
}
MAX_TOKENS = 256
DIMENSION = 384
METHODS = ("lexical_bm25", "dense_minilm")


class MiniLMEncoder:
    def __init__(self, model_dir: Path):
        for name, digest in MODEL_SHA256.items():
            if sha256_file(model_dir / name) != digest:
                raise ValueError(f"Model fingerprint mismatch: {name}.")
        import numpy
        import onnxruntime
        import tokenizers

        self.numpy = numpy
        self.tokenizer = tokenizers.Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=MAX_TOKENS)
        self.tokenizer.enable_padding(length=MAX_TOKENS, pad_id=self.tokenizer.token_to_id("[PAD]"))
        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self.session = onnxruntime.InferenceSession(
            str(model_dir / "onnx/model.onnx"), sess_options=options, providers=["CPUExecutionProvider"]
        )
        self.metadata = {
            "id": MODEL_ID, "revision": MODEL_REVISION, "files_sha256": MODEL_SHA256,
            "token_budget": MAX_TOKENS, "dimension": DIMENSION, "pooling": "attention_masked_mean_l2_normalized",
            "provider": "CPUExecutionProvider", "onnxruntime": onnxruntime.__version__,
            "numpy": numpy.__version__, "tokenizers": tokenizers.__version__,
        }

    def encode(self, texts: list[str]) -> list[list[float]]:
        encodings = self.tokenizer.encode_batch(texts)
        self.metadata["input_count"] = len(encodings)
        self.metadata["truncated_inputs"] = sum(bool(item.overflowing) for item in encodings)
        self.metadata["longest_input_tokens"] = max(sum(item.attention_mask) for item in encodings)
        np = self.numpy
        mask = np.asarray([item.attention_mask for item in encodings], dtype=np.int64)
        last_hidden, = self.session.run(["last_hidden_state"], {
            "input_ids": np.asarray([item.ids for item in encodings], dtype=np.int64),
            "attention_mask": mask,
            "token_type_ids": np.asarray([item.type_ids for item in encodings], dtype=np.int64),
        })
        if last_hidden.shape != (*mask.shape, DIMENSION):
            raise ValueError("Unexpected embedding model output shape.")
        pooled = (last_hidden * mask[..., None]).sum(axis=1) / mask.sum(axis=1, keepdims=True)
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        if not np.isfinite(norms).all() or not (norms > 0).all():
            raise ValueError("Embedding model returned an invalid vector.")
        return (pooled / norms).tolist()


def build_rankings(cases: list[dict], documents: dict[str, list], method: str,
                   encoder: MiniLMEncoder | None = None) -> list[dict]:
    if not cases or len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("Expected a nonempty list of unique synthetic cases.")
    for case in cases:
        if not set(case) <= set(CASE_FIELDS):
            raise ValueError("Ranking accepts case input fields only.")
        validate_case(case)
    if set(documents) != ALLOWED_CLAIMS:
        raise ValueError("Unexpected evidence claim inventory.")
    queries = [case_query_fields(case) for case in cases]

    if method == "lexical_bm25":
        tokenized = {claim_id: tokens(fields) for claim_id, fields in documents.items()}
        rankings = [rank_claims(bm25_scores(tokens(query), tokenized)) for query in queries]
    elif method == "dense_minilm" and encoder is not None:
        texts = [json.dumps(fields, ensure_ascii=False) for fields in [*documents.values(), *queries]]
        vectors = encoder.encode(texts)
        corpus_vectors = dict(zip(documents, vectors[:len(documents)], strict=True))
        rankings = [rank_claims({
            claim_id: math.fsum(x * y for x, y in zip(query, vector, strict=True))
            for claim_id, vector in corpus_vectors.items()
        }) for query in vectors[len(documents):]]
    else:
        raise ValueError("Dense ranking requires the pinned MiniLM encoder.")
    return [dict(case_id=case["case_id"], claim_ids=ids) for case, ids in zip(cases, rankings, strict=True)]


def run_pilot(encoder: MiniLMEncoder, documents: dict[str, list], k: int) -> dict:
    known = read_cases()
    cases = [entry["case"] for entry in known]
    rankings = {method: build_rankings(cases, documents, method, encoder) for method in METHODS}
    relevant = {entry["case"]["case_id"]: set(entry["matched_claim_ids"]) for entry in known}
    scores = {method: summarize_rankings([
        score_ranking(row["claim_ids"], relevant[row["case_id"]], k) for row in rows
    ]) for method, rows in rankings.items()}
    return {
        "reference_type": REFERENCE, "official_evaluation": False, "k": k, "case_count": len(cases),
        "claim_count": len(documents), "pilot_sha256": sha256_file(PILOT), "model": encoder.metadata,
        "metrics": scores, "rankings": rankings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pilot = commands.add_parser("pilot", help="Evaluate only the Task 07 development cases.")
    pilot.add_argument("--k", type=int, choices=range(1, len(ALLOWED_CLAIMS) + 1), default=3)
    rank = commands.add_parser("rank", help="Export rank lists in the Task 13 format from case inputs.")
    rank.add_argument("--method", choices=METHODS, default="dense_minilm")
    rank.add_argument("--cases", type=Path, required=True, help="JSON with a cases array; no reference labels.")
    rank.add_argument("--reference-sha256", required=True, help="Digest only, copied from the frozen reference.")
    for command in (pilot, rank):
        command.add_argument("--model-dir", type=Path, help="Local pinned tokenizer and ONNX weights.")
        command.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    try:
        needs_dense = args.command == "pilot" or args.method == "dense_minilm"
        if needs_dense and args.model_dir is None:
            raise ValueError("--model-dir is required for dense ranking.")
        encoder = MiniLMEncoder(args.model_dir) if needs_dense else None
        base, t790m, hashes = load_sources()
        documents = claim_text_fields(base, t790m)
        if args.command == "pilot":
            result = run_pilot(encoder, documents, args.k)
        else:
            if not re.fullmatch(r"[0-9a-fA-F]{64}", args.reference_sha256):
                raise ValueError("Reference SHA-256 must be a 64-digit hex digest.")
            raw_cases = args.cases.read_bytes()
            cases = json.loads(raw_cases)["cases"]
            rankings = build_rankings(cases, documents, args.method, encoder)
            result = {
                "system_id": args.method, "reference_sha256": args.reference_sha256.lower(),
                "cases": rankings, "case_input_sha256": hashlib.sha256(raw_cases).hexdigest(),
                "model": encoder.metadata if encoder else None,
            }
        result["oncokg_dataset_sha256"] = hashes
        write_json(args.output, result)
    except ImportError as error:
        parser.exit(1, f"STOP: Install requirements-dense.txt for dense retrieval ({error}).\n")
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"STOP: {error}\n")


if __name__ == "__main__":
    main()
