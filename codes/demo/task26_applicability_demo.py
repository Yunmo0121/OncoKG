"""Build and verify the offline Task 23–25 presentation bundle."""
from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile, ZipInfo

from task20_demo_bundle import json_bytes
from task25_trial_applicability import CONFLICT, MISSING, UNRESOLVED, run_demo

METHODS = {"task23": "Task 23 原规则", "task24_manual": "Task 24 手工标注", "task25": "Task 25 自动识别"}
ROW_LABELS = {"eligibility": "入组条件及出处", "review": "耐药复核来源"}
STATUS_LABELS = {
    CONFLICT: "存在入组条件冲突",
    MISSING: "需核对既往暴露",
    UNRESOLVED: "需核对分析人群",
    "CONTEXT_MATCHED": "保留原上下文状态",
}
CASE_LABELS = {
    "SYN-25-CONFLICT": "同亚组，暴露与排除条件冲突",
    "SYN-25-OTHER-POPULATION": "同试验，不同亚组",
    "SYN-25-MISSING-EXPOSURE": "同亚组，暴露缺失",
    "SYN-25-UNKNOWN-POPULATION": "同试验，亚组未知",
    "SYN-25-NO-CONFLICT": "同亚组，已知暴露不同",
}


def render_comparison(result: dict) -> str:
    cases = result["cases"]
    lines = [
        "# OncoKG · 三条证据的报告如何保留试验适用范围",
        "",
        f"本演示使用 {len(cases)} 个合成案例。每份报告最多展示 {result['k']} 条证据。"
        "前两条是同一虚构试验的两个结局，第三条在入组条件和耐药复核来源之间选择。",
        "",
        "| 合成场景 | Task 23 第三条 | Task 24 第三条 | Task 25 第三条 | Task 25 的结局说明 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for case in cases:
        methods = case["methods"]
        slots = [ROW_LABELS[methods[method]["selected"][-1]] for method in METHODS]
        status = methods["task25"]["report"]["evidence"][0]["context_status"]
        lines.append(f"| {' | '.join([CASE_LABELS[case['case_id']], *slots, STATUS_LABELS[status]])} |")

    lines.extend([
        "", "| 方法 | 漏保留的条件关联 | 多保留的条件关联 | 保留耐药复核来源的案例 |",
        "| --- | ---: | ---: | ---: |",
    ])
    for method, label in METHODS.items():
        reports = [case["methods"][method] for case in cases]
        missed = sum(len(report["missed_limit_links"]) for report in reports)
        extra = sum(len(report["extra_limit_links"]) for report in reports)
        review = sum(report["review_support_retained"] for report in reports)
        lines.append(f"| {label} | {missed} | {extra} | {review}/{len(cases)} |")

    conflict = next(case for case in cases if case["case_id"] == "SYN-25-CONFLICT")
    check = conflict["methods"]["task25"]["report"]["applicability_checks"][0]
    source = check["source_urls"][0]
    lines.extend([
        "",
        "## 两个案例演示",
        "",
        "1. **同一亚组有明确冲突。** 合成案例记录既往暴露 X，同亚组的入组条件排除了 X。"
        "Task 23 在第三位放入耐药复核来源。Task 24 依靠手工关联保留入组条件。"
        "Task 25 自动建立关联，并在两个结局旁提示该试验结果的直接适用性受限。"
        f"合成入组条件使用[占位出处]({source})。",
        "2. **限制来自同一试验的另一亚组。** 结局属于 A，入组条件属于 B。"
        "Task 25 避免交叉套用条件，第三位保留耐药复核来源。",
        "",
        "## 解读与复核",
        "",
        "四条预期关联来自两个案例，每个案例的一条入组条件对应两个结局。"
        "Task 24 的手工关联是本组固定样例的选择参照。"
        "这些数字来自工程测试，临床适用性及真实试验文档抽取仍需验证。",
        "",
        "`reports.json` 保存每个案例的结构化候选、初始排序和三种方法的完整报告。"
        "`manifest.json` 可用于核对包内文件。",
        "",
    ])
    return "\n".join(lines)


def build_entries() -> dict[str, bytes]:
    result = run_demo(include_inputs=True)
    entries = {
        "comparison.md": render_comparison(result).encode("utf-8"),
        "reports.json": json_bytes(result),
    }
    manifest = {
        "format": "oncokg-applicability-demo-v1",
        "official_evaluation": False,
        "cases": len(result["cases"]),
        "reports": sum(len(case["methods"]) for case in result["cases"]),
        "k": result["k"],
        "files_sha256": {name: sha256(content).hexdigest() for name, content in entries.items()},
    }
    return {**entries, "manifest.json": json_bytes(manifest)}


def verify_bundle(archive: ZipFile, entries: dict[str, bytes]) -> None:
    if sorted(archive.namelist()) != sorted(entries):
        raise ValueError("Unexpected or duplicate demo archive entries.")
    for name, content in entries.items():
        if archive.read(name) != content:
            raise ValueError(f"Saved demo file differs from the replay: {name}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "verify"))
    parser.add_argument("--bundle", required=True, type=Path)
    args = parser.parse_args()
    try:
        entries = build_entries()
        if args.command == "build":
            args.bundle.parent.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(dir=args.bundle.parent) as tmp:
                pending = Path(tmp) / "demo.zip"
                with ZipFile(pending, "x") as archive:
                    for name, data in sorted(entries.items()):
                        archive.writestr(ZipInfo(name), data, compress_type=ZIP_DEFLATED)
                with ZipFile(pending) as archive:
                    verify_bundle(archive, entries)
                args.bundle.hardlink_to(pending)
        else:
            with ZipFile(args.bundle) as archive:
                verify_bundle(archive, entries)
    except (OSError, ValueError, BadZipFile) as error:
        parser.exit(1, f"STOP: {error}\n")
    print(f"Verified applicability demo archive: {args.bundle}")


if __name__ == "__main__":
    main()
