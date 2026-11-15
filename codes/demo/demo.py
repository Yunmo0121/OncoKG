import json
from collections import defaultdict
from pathlib import Path


def progression_on(case, drug_id):
    outcomes = [event["outcome"] for event in case.get("history", []) if event["drug_id"] == drug_id]
    if "PROGRESSION" in outcomes:
        return True
    if "UNKNOWN" in outcomes or not case.get("history_complete", False):
        return None
    return False


def match_scope(claim, case):
    checks = [claim["disease_id"] == case["disease_id"]]
    for field in ("setting", "line", "region"):
        actual = case.get(field)
        if claim[field] != "ANY":
            checks.append(None if actual is None else actual == claim[field])
    variants = case.get("variants", {})
    checks.extend(variants.get(key) for key in claim["variant_ids"])
    if claim.get("condition_code"):
        checks.append(case.get("conditions", {}).get(claim["condition_code"]))
    if claim.get("prior_drug_id"):
        checks.append(progression_on(case, claim["prior_drug_id"]))
    if any(check is False for check in checks):
        return False
    return None if any(check is None for check in checks) else True


def trace(claims):
    return [
        {"claim_id": claim["id"], "evidence_ids": sorted(claim["evidence_ids"])}
        for claim in sorted(claims, key=lambda claim: claim["id"])
    ]


def evaluate(claims, case, *, filter_conflicts=True):
    by_drug = defaultdict(list)
    for claim in claims:
        if filter_conflicts or claim["kind"] == "SENSITIVITY":
            match = match_scope(claim, case)
            if match is not False:
                by_drug[claim["drug_id"]].append((claim, match))

    candidates = []
    pending_support = False
    for drug_id, rows in sorted(by_drug.items()):
        support = [claim for claim, match in rows if claim["kind"] == "SENSITIVITY" and match is True]
        if not support:
            pending_support = pending_support or any(claim["kind"] == "SENSITIVITY" for claim, _ in rows)
            continue

        conflicts = [claim for claim, match in rows if claim["kind"] != "SENSITIVITY" and match is True]
        pending = [claim for claim, match in rows if claim["kind"] != "SENSITIVITY" and match is None]
        if not filter_conflicts:
            status = "NOT_EVALUATED"
        elif any(claim["kind"] == "CONTRAINDICATION" for claim in conflicts):
            status = "BLOCKED"
        elif pending:
            status = "NEEDS_CONTEXT"
        elif conflicts:
            status = "REVIEW"
        else:
            status = "NO_RULE_HIT"

        candidates.append({
            "drug_id": drug_id, "status": status, "support": trace(support),
            "conflicts": trace(conflicts), "pending_rules": trace(pending),
        })

    status = "NEEDS_CONTEXT" if pending_support else "NO_MATCHING_EVIDENCE"
    if candidates:
        status = "CANDIDATES_FOUND"
    return {
        "status": status,
        "candidates": candidates,
        "forwarded_drug_ids": [
            item["drug_id"] for item in candidates
            if item["status"] in {"NO_RULE_HIT", "NOT_EVALUATED"}
        ],
    }


if __name__ == "__main__":
    seed = json.loads(Path("seed.json").read_text(encoding="utf-8"))
    case = json.loads(Path("case.json").read_text(encoding="utf-8"))
    if seed["manifest"]["mode"] != "DEMO":
        raise ValueError("demo.py expects a DEMO seed")
    for filter_conflicts in (True, False):
        result = evaluate(seed["claims"], case, filter_conflicts=filter_conflicts)
        print(json.dumps({"filter_conflicts": filter_conflicts, **result}, indent=2))