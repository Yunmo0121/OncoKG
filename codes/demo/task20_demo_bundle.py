"""Build or verify a reproducible local demonstration archive from saved rankings."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

from benchmark_task07 import sha256_file
from condition_retrieval import ALLOWED_CLAIMS, load_sources, offline_claims
from task07_retrieval_pilot import PILOT, read_cases
from task17_report_context import run_experiment
from task19_report_audit import check_fields, render_case, verify_report


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def build_entries(raw_rankings: bytes, case_id: str, k: int) -> dict[str, bytes]:
    if type(k) is not int or not 1 <= k <= len(ALLOWED_CLAIMS):
        raise ValueError("Evidence limit is outside the claim inventory.")
    base, t790m, hashes = load_sources()
    report = run_experiment(json.loads(raw_rankings), read_cases(), offline_claims(base, t790m),
                            hashes, sha256_file(PILOT), k, include_review_details=True)
    report["task15_report_sha256"] = hashlib.sha256(raw_rankings).hexdigest()
    entries = {"reports.json": json_bytes(report), "case-comparison.md": render_case(report, case_id).encode("utf-8")}
    manifest = {
        "format": "oncokg-development-demo-v1", "official_evaluation": False,
        "case_id": case_id, "k": k, "reports": sum(len(m["reports"]) for m in report["methods"].values()),
        "task15_report_sha256": report["task15_report_sha256"],
        "pilot_sha256": report["pilot_sha256"], "oncokg_dataset_sha256": hashes,
        "files_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in entries.items()},
    }
    return {**entries, "manifest.json": json_bytes(manifest)}


def verify_bundle(archive: ZipFile, raw_rankings: bytes) -> int:
    if sorted(archive.namelist()) != ["case-comparison.md", "manifest.json", "reports.json"]:
        raise ValueError("Unexpected or duplicate demo archive entries.")
    manifest = json.loads(archive.read("manifest.json"))
    expected = build_entries(raw_rankings, manifest["case_id"], manifest["k"])
    check_fields(manifest, json.loads(expected["manifest.json"]), "manifest")
    checked = verify_report(json.loads(archive.read("reports.json")), json.loads(expected["reports.json"]))
    for name, digest in manifest["files_sha256"].items():
        if hashlib.sha256(archive.read(name)).hexdigest() != digest:
            raise ValueError(f"Saved demo file differs from the replay: {name}.")
    return checked


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--case-id", default="SYN-PILOT-03")
    build.add_argument("--k", type=int, default=3)
    verify = commands.add_parser("verify")
    for command in (build, verify):
        command.add_argument("--rankings", type=Path, required=True)
        command.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    try:
        raw_rankings = args.rankings.read_bytes()
        if args.command == "build":
            entries = build_entries(raw_rankings, args.case_id, args.k)
            args.bundle.parent.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(dir=args.bundle.parent) as tmp:
                pending = Path(tmp) / "demo.zip"
                with ZipFile(pending, "x") as archive:
                    for name, data in sorted(entries.items()):
                        archive.writestr(ZipInfo(name), data, compress_type=ZIP_DEFLATED)
                with ZipFile(pending) as archive:
                    checked = verify_bundle(archive, raw_rankings)
                args.bundle.hardlink_to(pending)
        else:
            with ZipFile(args.bundle) as archive:
                checked = verify_bundle(archive, raw_rankings)
        print(f"Verified demo archive with {checked} development reports.")
    except (OSError, KeyError, TypeError, ValueError, AttributeError, BadZipFile) as error:
        parser.exit(1, f"STOP: {error}\n")


if __name__ == "__main__":
    main()
