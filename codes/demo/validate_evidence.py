"""Validate the first curated OncoKG evidence dataset.

Run from the OncoKG project root:
    python3 codes/demo/validate_evidence.py
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_FILE = PROJECT_ROOT / "data" / "curated" / "egfr_l858r_evidence_v0_1.json"


def validate(path: Path) -> list[str]:
    errors = []
    data = json.loads(path.read_text(encoding="utf-8"))
    claims = data.get("claims", [])

    if not data.get("research_only", False):
        errors.append("Dataset must be marked research_only.")
    if not claims:
        errors.append("Dataset must contain at least one claim.")

    ids = [claim.get("id") for claim in claims]
    if len(ids) != len(set(ids)):
        errors.append("Claim IDs must be unique.")

    for claim in claims:
        claim_id = claim.get("id", "<missing id>")
        if not claim.get("kind"):
            errors.append(f"{claim_id}: kind is required.")
        ev = claim.get("evidence", {})
        for key in ("id", "source_type", "source_url", "locator", "accessed_at"):
            if not ev.get(key):
                errors.append(f"{claim_id}: missing evidence.{key}.")
        if not ev.get("source_url", "").startswith("https://"):
            errors.append(f"{claim_id}: evidence source must have an HTTPS URL.")
        if claim.get("curation_status") != "source_checked_needs_independent_review":
            errors.append(f"{claim_id}: unexpected curation status.")

        if claim.get("kind") == "APPROVED_INDICATION":
            context = claim.get("clinical_context", {})
            if context.get("variant_alternative_operator") != "OR":
                errors.append(f"{claim_id}: variant alternatives must be OR.")
            if context.get("treatment_line") != "first_line":
                errors.append(f"{claim_id}: check treatment line.")
            if context.get("treatment_regimen") != "monotherapy":
                errors.append(f"{claim_id}: check treatment regimen.")

        if claim.get("kind") == "TRIAL_OUTCOME":
            outcome = claim.get("outcome", {})
            if outcome.get("is_l858r_only_result") is not False:
                errors.append(f"{claim_id}: overall trial result misclassified as L858R-only.")
            if claim.get("variant") is not None:
                errors.append(f"{claim_id}: overall trial result must not have a specific variant.")

    return errors


if __name__ == "__main__":
    if not EVIDENCE_FILE.exists():
        raise SystemExit(f"Evidence file not found: {EVIDENCE_FILE}")
    problems = validate(EVIDENCE_FILE)
    if problems:
        for problem in problems:
            print(f"ERROR: {problem}")
        raise SystemExit(1)
    data = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    print(f"PASS: validated {len(data['claims'])} traceable evidence claims.")
    for item in data["claims"]:
        print(f"  {item['id']} [{item['kind']}]")
