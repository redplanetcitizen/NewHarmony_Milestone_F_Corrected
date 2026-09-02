from __future__ import annotations

import csv
import json
from pathlib import Path

from .accounting import compute_accounts
from .adapter import solve_final_paths, write_rows
from .dashboard_data import build_dashboard
from .physical_accounting import compute_physical_accounts
from .source_guard import assert_unchanged, source_manifest, write_manifest


REPOSITORY = "https://github.com/redplanetcitizen/NewHarmony_Milestone_F_Corrected"


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def _validate_against_published(root: Path, annual_rows: list[dict]) -> list[dict]:
    checks = []
    for mode in sorted({row["technology_mode"] for row in annual_rows}):
        published = {
            int(row["year"]): row
            for row in _read_csv(root / "results" / "F_final" / mode / "annual_path.csv")
        }
        for row in annual_rows:
            if row["technology_mode"] != mode:
                continue
            reference = published[int(row["year"])]
            fields = {
                "fulfillment": "fulfillment",
                "harmony": "harmony",
                "investment_real_musd": "investment_real_musd",
                "stock_start_real_musd": "stock_start_real_musd",
                "stock_end_real_musd": "stock_end_real_musd",
                "gross_realized_real_musd": "gross_realized_real_musd",
            }
            for actual_field, reference_field in fields.items():
                actual = float(row[actual_field])
                expected = float(reference[reference_field])
                error = abs(actual - expected)
                tolerance = 1e-7 * max(1.0, abs(expected))
                checks.append(
                    {
                        "technology_mode": mode,
                        "year": int(row["year"]),
                        "field": actual_field,
                        "actual": actual,
                        "published": expected,
                        "absolute_error": error,
                        "tolerance": tolerance,
                        "passed": error <= tolerance,
                    }
                )
    return checks


def run_pipeline(milestone_root: Path, companion_root: Path, output_dir: Path) -> dict:
    milestone_root = milestone_root.resolve()
    companion_root = companion_root.resolve()
    output_dir = output_dir.resolve()
    required = [
        milestone_root / "code" / "new_harmony_empirical_f.py",
        milestone_root / "data" / "sectors_71.csv",
        milestone_root / "results" / "F_final" / "frozen" / "annual_path.csv",
        milestone_root / "results" / "F_final" / "historical" / "annual_path.csv",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Milestone F Corrected incompleto: " + ", ".join(missing))

    output_dir.mkdir(parents=True, exist_ok=True)
    before = source_manifest(milestone_root)
    write_manifest(before, output_dir / "SOURCE_MANIFEST_BEFORE.json")

    sector_rows, annual_rows = solve_final_paths(milestone_root, ("frozen", "historical"))
    write_rows(output_dir / "economic_sector_path.csv", sector_rows)
    write_rows(output_dir / "economic_annual_path.csv", annual_rows)

    ecological, contributions, coverage = compute_accounts(
        sector_rows,
        companion_root / "data" / "associazioni_ecologiche_qualitative_72x55.csv",
        companion_root / "data" / "crosswalk_f71_to_eco72.csv",
    )
    write_rows(output_dir / "ecological_summary.csv", ecological)
    write_rows(output_dir / "ecological_contributions.csv", contributions)
    write_rows(output_dir / "mapping_coverage.csv", coverage)

    physical, physical_contributions = compute_physical_accounts(
        sector_rows,
        companion_root / "data" / "coefficienti_ecologici_fisici_72x55.csv",
        companion_root / "data" / "baseline_output_fisico_2012.csv",
        companion_root / "data" / "crosswalk_f71_to_eco72.csv",
    )
    write_rows(output_dir / "physical_ecological_summary.csv", physical)
    write_rows(output_dir / "physical_ecological_contributions.csv", physical_contributions)

    after = source_manifest(milestone_root)
    write_manifest(after, output_dir / "SOURCE_MANIFEST_AFTER.json")
    assert_unchanged(before, after)
    checks = _validate_against_published(milestone_root, annual_rows)
    all_checks_passed = all(row["passed"] for row in checks)
    if not all_checks_passed:
        failed = [row for row in checks if not row["passed"]]
        raise RuntimeError(f"La riesecuzione non coincide con i risultati pubblicati: {failed[:3]}")

    source = {
        "repository": REPOSITORY,
        "commit": _read_commit(milestone_root),
        "tree_sha256": before["tree_sha256"],
    }
    dashboard = build_dashboard(
        annual_rows,
        ecological,
        contributions,
        coverage,
        source,
        sector_rows=sector_rows,
        physical_rows=physical,
        physical_contribution_rows=physical_contributions,
    )
    dashboard_path = output_dir / "dashboard.json"
    dashboard_path.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    static_data = companion_root / "dashboard" / "data.json"
    static_data.write_text(json.dumps(dashboard, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

    report = {
        "source": source,
        "source_unchanged": before["tree_sha256"] == after["tree_sha256"],
        "source_file_count": before["file_count"],
        "published_numeric_checks": len(checks),
        "published_numeric_checks_passed": all_checks_passed,
        "economic_sector_rows": len(sector_rows),
        "economic_annual_rows": len(annual_rows),
        "ecological_summary_rows": len(ecological),
        "ecological_contribution_rows": len(contributions),
        "physical_ecological_summary_rows": len(physical),
        "physical_ecological_contribution_rows": len(physical_contributions),
        "mapping_coverage": coverage,
        "solver_modified": False,
        "ecological_accounting_modes": ["qualitative_association", "physical_direct_mass"],
        "physical_coefficient_year": 2012,
        "physical_rebase": "activity_ratio_to_observed_real_2019",
    }
    (output_dir / "VALIDATION_REPORT.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def _read_commit(root: Path) -> str:
    head = root / ".git" / "HEAD"
    if not head.exists():
        provenance = root.parent / "ENGINE_PROVENANCE.json"
        if provenance.exists():
            return str(json.loads(provenance.read_text(encoding="utf-8"))["source_commit"])
        return "unknown"
    value = head.read_text(encoding="utf-8").strip()
    if value.startswith("ref: "):
        ref = root / ".git" / value[5:]
        if ref.exists():
            return ref.read_text(encoding="utf-8").strip()
        packed = root / ".git" / "packed-refs"
        if packed.exists():
            target = value[5:]
            for line in packed.read_text(encoding="utf-8").splitlines():
                if line and not line.startswith("#") and line.split()[-1] == target:
                    return line.split()[0]
    return value
