"""Compare lexical, dense, fused, and Neo4j evidence rankings on one snapshot."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from getpass import getpass
from pathlib import Path

from benchmark_task07 import sha256_file
from condition_retrieval import ALLOWED_CLAIMS, load_sources, offline_claims
from task07_retrieval_pilot import (
    PILOT, REFERENCE, STATUS_ORDER, claim_text_fields, rank_claims, read_cases, summarize_rankings,
)
from task08_multihop import HOP_BUDGETS, compare_cases
from task13_evaluation import score_claim_ranking, write_json
from task14_dense_retrieval import MiniLMEncoder, build_rankings

BASELINE = "lexical_bm25"
DENSE = "dense_minilm"
FUSED = "rrf_bm25_minilm"
RRF_K = 60


def reciprocal_rank_fusion(lexical: list[str], dense: list[str]) -> list[str]:
    scores = defaultdict(float)
    for ranking in (lexical, dense):
        for position, claim_id in enumerate(ranking, start=1):
            scores[claim_id] += 1 / (RRF_K + position)
    return rank_claims(scores)


def graph_ranking(paths: list[dict], lexical: list[str], *, contextual: bool) -> list[str]:
    lexical_position = {claim_id: i for i, claim_id in enumerate(lexical)}
    best = {}
    for path in paths:
        claim_id = path["claim_id"]
        priority = (
            STATUS_ORDER[path["context_status"]] if contextual else 0,
            path["hops"], lexical_position[claim_id],
        )
        if claim_id not in best or priority < best[claim_id]:
            best[claim_id] = priority
    return sorted(best, key=best.__getitem__)


def assemble_rankings(bm25_rows: list[dict], dense_rows: list[dict], graph_report: dict) -> dict:
    graph_by_case = {row["case_id"]: row["budgets"] for row in graph_report["cases"]}
    methods = {BASELINE: bm25_rows, DENSE: dense_rows, FUSED: []}
    for budget in HOP_BUDGETS:
        methods[f"kg_path_{budget}hop"] = []
        methods[f"kg_context_{budget}hop"] = []
    for lexical, dense in zip(bm25_rows, dense_rows, strict=True):
        case_id = lexical["case_id"]
        if dense["case_id"] != case_id:
            raise ValueError("Lexical and dense rankings must use the same ordered cases.")
        order = lexical["claim_ids"]
        methods[FUSED].append(dict(case_id=case_id,
                                   claim_ids=reciprocal_rank_fusion(order, dense["claim_ids"])))
        for budget in HOP_BUDGETS:
            paths = graph_by_case[case_id][str(budget)]["paths"]
            for variant in ("path", "context"):
                methods[f"kg_{variant}_{budget}hop"].append(dict(
                    case_id=case_id, claim_ids=graph_ranking(paths, order, contextual=variant == "context"),
                ))
    return methods


def compare_pilot(rankings: dict, known: list[dict], k: int) -> dict:
    reference = {entry["case"]["case_id"]: set(entry["matched_claim_ids"]) for entry in known}
    lexical_tops = {row["case_id"]: row["claim_ids"][:k] for row in rankings[BASELINE]}
    overall, diagnostics = {}, {}
    for method, rows in rankings.items():
        scores, changes = [], []
        for row in rows:
            case_id, ranking = row["case_id"], row["claim_ids"]
            relevant = reference[case_id]
            score = score_claim_ranking(ranking, relevant, k)
            scores.append(score)
            top = ranking[:k]
            before = lexical_tops[case_id]
            gained = [claim for claim in top if claim not in before]
            lost = [claim for claim in before if claim not in top]
            changes.append({
                "case_id": case_id, "top_k": top, **score,
                "reference_claim_ids": sorted(relevant),
                "added_vs_bm25": gained, "removed_vs_bm25": lost,
                "gained_reference_claim_ids": [claim for claim in gained if claim in relevant],
                "lost_reference_claim_ids": [claim for claim in lost if claim in relevant],
            })
        overall[method] = summarize_rankings(scores)
        diagnostics[method] = changes
    return {"metrics": overall, "diagnostics": diagnostics}


def retrieve(cases: list[dict], encoder: MiniLMEncoder, args) -> tuple[dict, dict, dict]:
    from neo4j import GraphDatabase

    base, t790m, hashes = load_sources()
    documents = claim_text_fields(base, t790m)
    lexical = build_rankings(cases, documents, BASELINE)
    dense = build_rankings(cases, documents, DENSE, encoder)
    auth = (args.user, getpass("Neo4j password: "))
    with GraphDatabase.driver(args.uri, auth=auth) as driver:
        with driver.session(database=args.database) as session:
            graph = session.execute_read(compare_cases, cases, offline_claims(base, t790m), hashes)
    return assemble_rankings(lexical, dense, graph), graph, hashes


def main() -> None:
    from neo4j.exceptions import DriverError, Neo4jError

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pilot = commands.add_parser("pilot", help="Benchmark the eight Task 07 development cases.")
    pilot.add_argument("--k", type=int, choices=range(1, len(ALLOWED_CLAIMS) + 1), default=3)
    pilot.add_argument("--output", type=Path, required=True)
    rank = commands.add_parser("rank", help="Export all seven systems for Task 13 scoring.")
    rank.add_argument("--cases", type=Path, required=True, help="JSON with a case-only cases array.")
    rank.add_argument("--reference-sha256", required=True)
    rank.add_argument("--output-dir", type=Path, required=True)
    for command in (pilot, rank):
        command.add_argument("--model-dir", type=Path, required=True)
        command.add_argument("--uri", default="bolt://localhost:7687")
        command.add_argument("--database", default="neo4j")
        command.add_argument("--user", default="neo4j")
    args = parser.parse_args()
    try:
        if args.command == "pilot":
            known = read_cases()
            cases = [entry["case"] for entry in known]
        else:
            if not re.fullmatch(r"[0-9a-fA-F]{64}", args.reference_sha256):
                raise ValueError("Reference SHA-256 must be a 64-digit hex digest.")
            raw_cases = args.cases.read_bytes()
            payload = json.loads(raw_cases)
            if "annotations" in payload:
                raise ValueError("Pass a case-only dataset without reference labels.")
            cases = payload["cases"]
            if args.output_dir.exists():
                raise FileExistsError(f"Output directory already exists: {args.output_dir}")

        encoder = MiniLMEncoder(args.model_dir)
        rankings, graph, hashes = retrieve(cases, encoder, args)
        metadata = {"oncokg_dataset_sha256": hashes, "graph_origin": graph["origin"],
                    "dense_model": encoder.metadata, "rrf_k": RRF_K}
        if args.command == "pilot":
            write_json(args.output, {
                **metadata, **compare_pilot(rankings, known, args.k),
                "reference_type": REFERENCE, "official_evaluation": False,
                "pilot_sha256": sha256_file(PILOT), "k": args.k, "rankings": rankings,
                "graph_paths": graph["cases"],
            })
        else:
            args.output_dir.mkdir(parents=True, exist_ok=False)
            for method, rows in rankings.items():
                write_json(args.output_dir / f"{method}.json", {
                    **metadata, "system_id": method, "cases": rows,
                    "reference_sha256": args.reference_sha256.lower(),
                    "case_input_sha256": hashlib.sha256(raw_cases).hexdigest(),
                })
    except (DriverError, Neo4jError) as error:
        parser.exit(1, f"STOP: Neo4j operation failed ({type(error).__name__}).\n")
    except (ImportError, OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"STOP: {error}\n")


if __name__ == "__main__":
    main()
