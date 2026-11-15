"""OncoKG Task 04: read-only, research-only context matching.

Two modes:
  --offline : uses copies of the existing *curated* JSON records as a preview.
  --db      : verifies BOTH Dataset SHA256 markers, 23/32 graph counts, and
              reads Claims/relations from the user's OncoKG-Real Neo4j instance.

Never writes to Neo4j. Never produces individual clinical recommendations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from getpass import getpass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE_FILE = ROOT / "data/curated/egfr_l858r_evidence_v0_1.json"
T790M_FILE = ROOT / "data/curated/egfr_t790m_evidence_extraction_v0_2.json"
CASES_FILE = ROOT / "data/samples/synthetic_nsclc_cases_v0_1.json"
BASE_ID = "ONCOKG-NSCLC-EGFR-REAL-EVIDENCE-V0.1"
T790M_ID = "ONCOKG-NSCLC-EGFR-T790M-EXTRACTION-V0.2"
ALLOWED_CLAIMS = {
    "FDA-TAGRISSO-2026-1.3-EGFR-L858R",
    "FLAURA-2018-EGFR-MUTATED-OVERALL-PFS",
    "FDA-TAGRISSO-EGFR-T790M-POST-TKI",
    "AURA3-2017-T790M-OVERALL-PFS",
    "PAO-2005-T790M-GEFITINIB-ERLOTINIB-RESISTANCE",
}


def source_data(path: Path):
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def load_sources():
    base, bsha = source_data(BASE_FILE)
    t790m, tsha = source_data(T790M_FILE)
    if base.get("dataset_id") != BASE_ID or t790m.get("dataset_id") != T790M_ID:
        raise ValueError("Unexpected dataset versions; review input files before proceeding.")
    return base, t790m, {BASE_ID: bsha, T790M_ID: tsha}


def offline_claims(base: dict, t790m: dict):
    """Approximate *graph-shaped* rows from curated records, without Neo4j access."""
    rows = []
    for dataset_id, dataset in ((BASE_ID, base), (T790M_ID, t790m)):
        for claim in dataset["claims"]:
            is_old = dataset_id == BASE_ID
            if is_old:
                variant = [] if claim["variant"] is None else ["L858R"]
                drugs = [claim["drug"]]
                url = claim["evidence"]["source_url"]
                context = claim["clinical_context"]
                prior_classes = []
                progressions = []
            else:
                variant = ["T790M"]
                drugs = claim.get("drugs", [claim.get("drug")])
                url = claim["source"]["url"]
                context = claim["clinical_context"]
                prior_classes = ["EGFR tyrosine kinase inhibitor"] if claim["kind"] != "RESISTANCE_ASSOCIATION" else []
                progressions = {
                    "APPROVED_INDICATION": ["PROGRESSION:ON_OR_AFTER_EGFR_TKI"],
                    "TRIAL_OUTCOME": ["PROGRESSION:DURING_FIRST_LINE_EGFR_TKI"],
                    "RESISTANCE_ASSOCIATION": ["PROGRESSION:AFTER_GEFITINIB_OR_ERLOTINIB"],
                }[claim["kind"]]
            rows.append({
                "dataset_id": dataset_id,
                "id": claim["id"],
                "kind": claim["kind"],
                "context_json": json.dumps(context),
                "variants": variant,
                "drugs": drugs,
                "diseases": ["NSCLC"],
                "prior_classes": prior_classes,
                "progressions": progressions,
                "evidence_urls": [url],
                "curation_status": claim["curation_status"],
            })
    return rows


def read_db_tx(tx, source_hashes: dict):
    """Transaction contains only MATCH/RETURN queries; never CREATE/SET/MERGE."""
    node_count = tx.run("MATCH (n) RETURN count(n) AS n").single(strict=True)["n"]
    link_count = tx.run("MATCH ()-[r]->() RETURN count(r) AS r").single(strict=True)["r"]
    if (node_count, link_count) != (23, 32):
        raise ValueError(f"Database is not expected v0.2 (got {node_count} nodes / {link_count} relationships). STOP.")

    marker_rows = tx.run(
        "MATCH (d:Dataset) WHERE d.id IN $ids "
        "RETURN d.id AS id, d.source_sha256 AS sha",
        ids=list(source_hashes),
    ).data()
    markers = {r["id"]: r["sha"] for r in marker_rows}
    if markers != source_hashes:
        raise ValueError("Dataset SHA256 does not match your local curated JSON. Wrong database or changed files. STOP.")

    query = """
        MATCH (ds:Dataset)-[:CONTAINS_CLAIM]->(c:Claim)
        WHERE ds.id IN $ids
        MATCH (c)-[:IN_DISEASE]->(dis:Disease)
        MATCH (c)-[:HAS_EVIDENCE]->(ev:Evidence)
        OPTIONAL MATCH (c)-[:REQUIRES_VARIANT]->(v:Variant)
        OPTIONAL MATCH (c)-[:ABOUT_DRUG]->(dr:Drug)
        OPTIONAL MATCH (c)-[:REQUIRES_PRIOR_TREATMENT_CLASS]->(tc:TreatmentClass)
        OPTIONAL MATCH (c)-[:HAS_PROGRESSION_CONTEXT]->(pc:ProgressionContext)
        RETURN ds.id AS dataset_id, c.id AS id, c.kind AS kind,
               c.clinical_context_json AS context_json,
               collect(DISTINCT v.protein_label) AS variants,
               collect(DISTINCT dr.name) AS drugs,
               collect(DISTINCT dis.code) AS diseases,
               collect(DISTINCT tc.name) AS prior_classes,
               collect(DISTINCT pc.id) AS progressions,
               collect(DISTINCT ev.url) AS evidence_urls,
               c.curation_status AS curation_status
        ORDER BY id
    """
    records = tx.run(query, ids=list(source_hashes)).data()
    verify_records(records)
    return records


def verify_records(records: list[dict]):
    ids = [r["id"] for r in records]
    if len(ids) != 5 or set(ids) != ALLOWED_CLAIMS or len(set(ids)) != 5:
        raise ValueError("Unexpected Claim IDs or duplicate claims; stop rather than evaluate incomplete evidence.")
    for row in records:
        if row["diseases"] != ["NSCLC"] or len(row["evidence_urls"]) != 1:
            raise ValueError(f"Incomplete disease/source linkage for {row['id']}.")
        if row["curation_status"] != "source_checked_needs_independent_review":
            raise ValueError("Unexpected clinical review status; do not use this evaluator.")
        expected_variants = [] if row["id"].startswith("FLAURA-") else ["L858R" if row["id"].endswith("EGFR-L858R") else "T790M"]
        if row["variants"] != expected_variants:
            raise ValueError(f"Incorrect variant linkage for {row['id']}.")
        if row["id"].startswith("PAO-"):
            if sorted(row["drugs"]) != ["erlotinib", "gefitinib"]:
                raise ValueError("Resistance association drug links unexpectedly changed.")
        elif row["drugs"] != ["osimertinib"]:
            raise ValueError("Unexpected ABOUT_DRUG links.")
        if row["id"].startswith("FDA-TAGRISSO-EGFR-T790M"):
            if row["progressions"] != ["PROGRESSION:ON_OR_AFTER_EGFR_TKI"] or row["prior_classes"] != ["EGFR tyrosine kinase inhibitor"]:
                raise ValueError("T790M FDA prior-therapy/progression graph links are incomplete.")
        if row["id"].startswith("AURA3-"):
            if row["progressions"] != ["PROGRESSION:DURING_FIRST_LINE_EGFR_TKI"] or row["prior_classes"] != ["EGFR tyrosine kinase inhibitor"]:
                raise ValueError("AURA3 prior-therapy/progression graph links are incomplete.")
    return True


def verify_against_curated(rows: list[dict], expected_rows: list[dict]):
    """Check read graph links/context match versioned source JSON, not just counts."""
    actual = {r["id"]: r for r in rows}
    expected = {r["id"]: r for r in expected_rows}
    if set(actual) != set(expected):
        raise ValueError("Neo4j Claim inventory differs from curated inputs.")
    for cid in expected:
        a, e = actual[cid], expected[cid]
        for field in ("dataset_id", "kind", "curation_status"):
            if a[field] != e[field]:
                raise ValueError(f"Neo4j/curated mismatch at {cid}: {field}")
        for field in ("variants", "drugs", "diseases", "prior_classes", "progressions", "evidence_urls"):
            if sorted(a[field]) != sorted(e[field]):
                raise ValueError(f"Neo4j/curated relationship mismatch at {cid}: {field}")
        if json.loads(a["context_json"]) != json.loads(e["context_json"]):
            raise ValueError(f"Neo4j/curated clinical context mismatch at {cid}.")
    return True


def validate_case(case: dict):
    if case.get("synthetic") is not True or not isinstance(case.get("case_id"), str):
        raise ValueError("Only labelled synthetic cases are supported; do NOT submit real patient information.")
    if case.get("cancer_type") != "NSCLC" or case.get("gene") != "EGFR":
        raise ValueError("This prototype only covers NSCLC/EGFR.")
    variants = case.get("variants")
    if not isinstance(variants, list) or not variants or any(v not in {"L858R", "T790M"} for v in variants):
        raise ValueError("Use a nonempty variants list containing only L858R and/or T790M.")
    bool_fields = (
        "prior_egfr_tki", "progression_on_or_after_egfr_tki",
        "progression_during_first_line_egfr_tki", "progression_after_prior_drug",
        "fda_approved_egfr_test", "fda_approved_t790m_test",
    )
    for field in bool_fields:
        if field in case and case[field] is not None and type(case[field]) is not bool:
            raise ValueError(f"{field} must be true, false, or null (unknown).")
    if case.get("prior_drugs") is not None:
        if not isinstance(case["prior_drugs"], list) or any(not isinstance(x, str) for x in case["prior_drugs"]):
            raise ValueError("prior_drugs must be a list of drug names or null (unknown).")


def check_equal(case: dict, field: str, expected, description: str):
    value = case.get(field)
    if value is None:
        return None, f"MISSING: {description} ({field})"
    matched = value == expected
    return matched, f"{'MATCH' if matched else 'MISMATCH'}: {description}; supplied={value!r}"


def check_one_of(case: dict, field: str, options: tuple, description: str):
    value = case.get(field)
    if value is None:
        return None, f"MISSING: {description} ({field})"
    matched = value in options
    return matched, f"{'MATCH' if matched else 'MISMATCH'}: {description}; supplied={value!r}"


def match_claim(case: dict, claim: dict):
    """Pure tri-state checks: NOT_MATCHED overrides missing; never recommends treatment."""
    cid = claim["id"]
    context = json.loads(claim["context_json"])
    if not claim["variants"]:
        return "NOT_EVALUATED", ["No specific variant relation: overall FLAURA outcome is not classified for an individual variant here."]
    if not set(case["variants"]) & set(claim["variants"]):
        return "NOT_MATCHED", ["MISMATCH: no matching variant in this Claim's explicit REQUIRES_VARIANT relation."]

    checks = []
    if cid == "FDA-TAGRISSO-2026-1.3-EGFR-L858R":
        checks = [
            check_equal(case, "age_group", "adult", "adult population"),
            check_equal(case, "disease_stage", "metastatic", "metastatic disease"),
            check_equal(case, "treatment_line", "first_line", "first-line context"),
            check_equal(case, "fda_approved_egfr_test", True, "FDA-approved EGFR test confirmation"),
        ]
    elif cid == "FDA-TAGRISSO-EGFR-T790M-POST-TKI":
        checks = [
            check_equal(case, "age_group", "adult", "adult population"),
            check_equal(case, "disease_stage", "metastatic", "metastatic disease"),
            check_equal(case, "prior_egfr_tki", True, "prior EGFR-TKI therapy"),
            check_equal(case, "progression_on_or_after_egfr_tki", True, "progression on/after EGFR-TKI"),
            check_equal(case, "fda_approved_t790m_test", True, "FDA-approved T790M test confirmation"),
        ]
    elif cid == "AURA3-2017-T790M-OVERALL-PFS":
        checks = [
            check_one_of(case, "disease_stage", ("advanced", "metastatic"), "advanced-stage trial context"),
            check_equal(case, "prior_egfr_tki", True, "prior EGFR-TKI therapy"),
            check_equal(case, "prior_treatment_line", "first_line", "progression after first-line EGFR-TKI"),
            check_equal(case, "progression_during_first_line_egfr_tki", True, "progression during first-line EGFR-TKI"),
        ]
    elif cid == "PAO-2005-T790M-GEFITINIB-ERLOTINIB-RESISTANCE":
        prior = case.get("prior_drugs")
        if prior is None:
            drug_check = (None, "MISSING: prior drug names (prior_drugs)")
        else:
            overlap = sorted(set(x.lower().strip() for x in prior) & {"gefitinib", "erlotinib"})
            drug_check = (bool(overlap), f"{'MATCH' if overlap else 'MISMATCH'}: specific gefitinib/erlotinib exposure; overlap={overlap}")
        checks = [
            check_equal(case, "histology", "adenocarcinoma", "lung adenocarcinoma research context"),
            drug_check,
            check_equal(case, "progression_after_prior_drug", True, "progression after named drug"),
        ]
    else:
        return "NOT_EVALUATED", ["No validated matching rule for this Claim."]

    # Keep the source-derived context attached to each Claim; no inferred hard contraindication.
    if not context:
        return "NOT_EVALUATED", ["Missing stored clinical context."]
    status = "NOT_MATCHED" if any(result is False for result, _ in checks) else (
        "NEEDS_INFORMATION" if any(result is None for result, _ in checks) else "CONTEXT_MATCHED"
    )
    return status, [message for _, message in checks]


def evaluate(case: dict, rows: list[dict], origin: str):
    validate_case(case)
    verify_records(rows)
    results = []
    for row in sorted(rows, key=lambda r: r["id"]):
        status, checks = match_claim(case, row)
        results.append({
            "claim_id": row["id"],
            "claim_type": row["kind"],
            "status": status,
            "drugs_mentioned_not_recommended": row["drugs"],
            "checks": checks,
            "source_urls": row["evidence_urls"],
            "curation_status": row["curation_status"],
            "warning": ("Historical resistance association for research review only; NOT a contraindication or automatic drug block."
                        if row["kind"] == "RESISTANCE_ASSOCIATION" else
                        "Context matching does not establish patient-level eligibility or clinical suitability."),
        })
    return {
        "case_id": case["case_id"],
        "synthetic": True,
        "data_origin": origin,
        "research_only": True,
        "disclaimer": "Research-only, rule-based evidence-context exercise; NOT clinical advice, eligibility determination or drug recommendation.",
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="OncoKG Task 04 read-only context matcher (synthetic cases ONLY)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true", help="Preview against curated JSON; does NOT query Neo4j")
    mode.add_argument("--db", action="store_true", help="Verify hashes/counts and query OncoKG-Real (read-only)")
    parser.add_argument("--case-id", default="SYN-T790M-001")
    parser.add_argument("--cases", type=Path, default=CASES_FILE)
    parser.add_argument("--output", type=Path, help="Optional local JSON report path (no database writes)")
    parser.add_argument("--uri", default="bolt://localhost:7687")
    parser.add_argument("--username", default="neo4j")
    parser.add_argument("--database", default="neo4j")
    args = parser.parse_args()
    try:
        cases_data = json.loads(args.cases.read_text(encoding="utf-8"))
        cases = cases_data["cases"]
        matches = [c for c in cases if c.get("case_id") == args.case_id]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one synthetic case named {args.case_id}.")
        case = matches[0]
        validate_case(case)
        baseline, t790m, hashes = load_sources()
        if args.offline:
            rows = offline_claims(baseline, t790m)
            origin = "offline_curated_json_preview_NO_NEO4J_QUERY"
        else:
            # Import only when online mode is explicitly chosen.
            from neo4j import GraphDatabase
            with GraphDatabase.driver(args.uri, auth=(args.username, getpass("Password for OncoKG-Real: "))) as driver:
                driver.verify_connectivity()
                with driver.session(database=args.database) as session:
                    rows = session.execute_read(read_db_tx, hashes)
            verify_against_curated(rows, offline_claims(baseline, t790m))
            origin = "verified_neo4j_oncokg_real_read_only"
        report = evaluate(case, rows, origin)
        print(f"PASS: {len(report['results'])} claims evaluated for {case['case_id']} ({origin}).")
        for r in report["results"]:
            print(f"  {r['status']:<18} {r['claim_id']}")
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"Report written locally: {args.output}")
        else:
            print("Tip: add --output docs/results/task04_case_result.json to save a reproducible report.")
        print("No Neo4j write operation performed. Not for clinical use.")
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(1, f"STOP: {exc}\n")
    except Exception as exc:
        # Dependency/connection failures are reported without dumping passwords.
        parser.exit(1, f"DATABASE/DRIVER ERROR: {type(exc).__name__}: {exc}\n")


if __name__ == "__main__":
    main()
