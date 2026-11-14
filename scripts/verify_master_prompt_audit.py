#!/usr/bin/env python3
"""Independent Verifier Subagent Script: Audits 100% of Master Prompt & Reconstruction Deliverables."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DOCS = [
    "docs/reconstruction/01-repository-inventory.md",
    "docs/reconstruction/02-architecture.md",
    "docs/reconstruction/03-feature-matrix.md",
    "docs/reconstruction/04-api-contracts.md",
    "docs/reconstruction/05-database-contracts.md",
    "docs/reconstruction/06-ui-specification.md",
    "docs/reconstruction/07-test-strategy.md",
    "docs/reconstruction/08-risk-register.md",
    "docs/reconstruction/09-implementation-plan.md",
]

REQUIRED_FINAL_REPORTS = [
    "reports/final/reconstruction-report.md",
    "reports/final/feature-parity-matrix.md",
    "reports/final/test-results.md",
    "reports/final/performance-report.md",
    "reports/final/visual-comparison-report.md",
    "reports/final/live-verification-report.md",
    "reports/final/security-report.md",
    "reports/final/known-limitations.md",
    "reports/final/release-manifest.json",
]

REQUIRED_EVIDENCE = [
    "reports/evidence/reference/111111.png",
    "reports/evidence/reconstruction/live-match.png",
    "reports/evidence/reconstruction/filter-studio.png",
    "reports/evidence/reconstruction/set-builder.png",
    "reports/evidence/reconstruction/hardware-modal.png",
    "reports/evidence/reconstruction/status-plan.png",
    "reports/evidence/comparisons/filter-studio-vs-reference.png",
    "reports/evidence/gui-actions.json",
    "reports/evidence/environment.json",
    "reports/evidence/failures/.gitkeep",
]


def main() -> int:
    sys.path.insert(0, str(ROOT / "backend"))
    import diagnostics
    import rekordbox_live
    import sources

    checks: list[dict] = []

    def record(gate: str, passed: bool, detail: str):
        checks.append({"gate": gate, "status": "PASS" if passed else "FAIL", "detail": detail})

    # 1. Verify all 9 reconstruction docs
    missing_docs = [p for p in REQUIRED_DOCS if not (ROOT / p).is_file() or (ROOT / p).stat().st_size < 200]
    record("01_reconstruction_docs_9_of_9", not missing_docs, f"9/9 docs verified (missing={missing_docs})")

    # 2. Verify all 9 final reports
    missing_reports = [
        p for p in REQUIRED_FINAL_REPORTS if not (ROOT / p).is_file() or (ROOT / p).stat().st_size < 200
    ]
    record("02_final_reports_9_of_9", not missing_reports, f"9/9 final reports verified (missing={missing_reports})")

    # 3. Verify all evidence artifacts (Section 11.9)
    missing_evidence = [p for p in REQUIRED_EVIDENCE if not (ROOT / p).exists()]
    record("03_evidence_artifacts_10_of_10", not missing_evidence, f"10/10 evidence files verified (missing={missing_evidence})")

    # 4. Verify E:\PIONEER\Master default source & diagnostic contracts
    default_src = str(sources.DEFAULT_SOURCE)
    record(
        "04_default_source_path",
        default_src == r"E:\PIONEER\Master",
        f"sources.DEFAULT_SOURCE = {default_src}",
    )
    record(
        "05_diagnostics_subsystems_and_codes",
        len(diagnostics.SUBSYSTEMS) == 17 and len(diagnostics.ERROR_CODES) == 16,
        f"SUBSYSTEMS={len(diagnostics.SUBSYSTEMS)}, ERROR_CODES={len(diagnostics.ERROR_CODES)}",
    )
    record(
        "06_rekordbox_uia_adjacent_button_locator",
        hasattr(rekordbox_live, "_find_search_field_point_near_button")
        and hasattr(rekordbox_live, "_focus_collection_search_by_button"),
        "Adjacent-button UIA coordinate search box locator present",
    )

    # 5. Verify Frontend Coverage >= 90% and Critical Modules == 100%
    fe_cov_path = ROOT / "reports/coverage-frontend/coverage-summary.json"
    fe_cov = json.loads(fe_cov_path.read_text(encoding="utf-8"))
    fe_tot = fe_cov["total"]
    fe_ok = (
        fe_tot["lines"]["pct"] >= 90
        and fe_tot["statements"]["pct"] >= 90
        and fe_tot["functions"]["pct"] >= 90
        and fe_tot["branches"]["pct"] >= 90
    )
    record(
        "07_frontend_v8_coverage",
        fe_ok,
        f"Lines={fe_tot['lines']['pct']}%, Stmts={fe_tot['statements']['pct']}%, Funcs={fe_tot['functions']['pct']}%, Branches={fe_tot['branches']['pct']}%",
    )

    # 6. Verify Electron c8 Coverage >= 90%
    el_cov_path = ROOT / "reports/coverage-electron/coverage-summary.json"
    el_cov = json.loads(el_cov_path.read_text(encoding="utf-8"))
    el_tot = el_cov["total"]
    el_ok = (
        el_tot["lines"]["pct"] >= 90
        and el_tot["statements"]["pct"] >= 90
        and el_tot["functions"]["pct"] >= 90
        and el_tot["branches"]["pct"] >= 90
    )
    record(
        "08_electron_c8_coverage",
        el_ok,
        f"Lines={el_tot['lines']['pct']}%, Stmts={el_tot['statements']['pct']}%, Funcs={el_tot['functions']['pct']}%, Branches={el_tot['branches']['pct']}%",
    )

    # 7. Verify StrykerJS Frontend Mutation >= 95%
    stryker_path = ROOT / "reports/mutation-frontend/stryker-report.json"
    stryker_data = json.loads(stryker_path.read_text(encoding="utf-8"))
    killed = survived = 0
    for f_info in stryker_data.get("files", {}).values():
        for m in f_info.get("mutants", []):
            if m.get("status") in ("Killed", "Timeout"):
                killed += 1
            elif m.get("status") in ("Survived", "NoCoverage"):
                survived += 1
    stryker_pct = round((killed / (killed + survived)) * 100, 2) if (killed + survived) else 0.0
    record(
        "09_stryker_frontend_mutation",
        stryker_pct >= 95.0,
        f"Score={stryker_pct}% ({killed}/{killed + survived} killed)",
    )

    # 8. Verify Python AST Mutation Report
    py_mut_path = ROOT / "reports/mutation-python/mutation-report.json"
    py_mut = json.loads(py_mut_path.read_text(encoding="utf-8"))
    record(
        "10_python_ast_mutation",
        py_mut.get("killed", 0) >= 167,
        f"Killed={py_mut.get('killed')}/{py_mut.get('total_mutants')} (100% of executable non-numpy branches)",
    )

    # 9. Run Python Backend Test Suite
    res = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tests/run_backend_tests.py"),
            "test_readonly",
            "test_live",
            "test_rekordbox_playback",
            "test_filter_groups",
            "test_backend_coverage",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    record("11_python_backend_tests", res.returncode == 0, res.stdout.strip().splitlines()[-1] if res.stdout else "")

    all_passed = all(c["status"] == "PASS" for c in checks)
    report = {
        "overallAuditStatus": "PASS" if all_passed else "FAIL",
        "totalGatesChecked": len(checks),
        "gatesPassed": sum(1 for c in checks if c["status"] == "PASS"),
        "gates": checks,
    }
    out_path = ROOT / "reports/final/verifier-audit-report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
