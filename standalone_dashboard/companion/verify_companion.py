from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica gli output del companion ecologico")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    out = (args.output_dir or (root / "outputs")).resolve()
    required = [
        "economic_sector_path.csv",
        "economic_annual_path.csv",
        "ecological_summary.csv",
        "ecological_contributions.csv",
        "physical_ecological_summary.csv",
        "physical_ecological_contributions.csv",
        "mapping_coverage.csv",
        "dashboard.json",
        "SOURCE_MANIFEST_BEFORE.json",
        "SOURCE_MANIFEST_AFTER.json",
        "VALIDATION_REPORT.json",
    ]
    missing = [name for name in required if not (out / name).is_file()]
    if missing:
        raise SystemExit("Output mancanti: " + ", ".join(missing))
    before = json.loads((out / "SOURCE_MANIFEST_BEFORE.json").read_text(encoding="utf-8"))
    after = json.loads((out / "SOURCE_MANIFEST_AFTER.json").read_text(encoding="utf-8"))
    report = json.loads((out / "VALIDATION_REPORT.json").read_text(encoding="utf-8"))
    dashboard = json.loads((out / "dashboard.json").read_text(encoding="utf-8"))
    checks = {
        "source_manifest_identical": before["tree_sha256"] == after["tree_sha256"],
        "report_confirms_source_unchanged": report["source_unchanged"] is True,
        "published_numeric_checks_passed": report["published_numeric_checks_passed"] is True,
        "solver_not_modified": report["solver_modified"] is False,
        "dashboard_solver_not_modified": dashboard["meta"]["solver_modified"] is False,
        "two_technology_modes": set(dashboard["modes"]) == {"frozen", "historical"},
        "fifty_five_pollutants": len(dashboard["pollutants"]) == 55,
        "forty_nine_physical_pollutants": len(dashboard.get("physical_pollutants", [])) == 49,
        "sector_selector_catalogue": len(dashboard.get("sectors", [])) == 71,
        "mapped_and_unmapped_sectors_marked": (
            sum(bool(row["ecologically_mapped"]) for row in dashboard.get("sectors", [])) == 66
            and sum(not bool(row["ecologically_mapped"]) for row in dashboard.get("sectors", [])) == 5
        ),
        "qualitative_associations_in_dashboard": all(
            len(mode_data.get("qualitative_associations", [])) > 0
            for mode_data in dashboard["modes"].values()
        ),
        "physical_contributions_in_dashboard": all(
            len(mode_data.get("physical_sector_contributions", [])) > 0
            for mode_data in dashboard["modes"].values()
        ),
        "sector_economic_paths_in_dashboard": all(
            len(mode_data.get("sector_economy", [])) > 0
            for mode_data in dashboard["modes"].values()
        ),
        "sector_diagnostics_present": all(
            all("gross_requirement_coverage" in row and "diagnostic_sector_harmony" in row
                for row in mode_data.get("sector_economy", []))
            for mode_data in dashboard["modes"].values()
        ),
    }
    for label, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'} {label}")
    if not all(checks.values()):
        return 1
    print(f"PASS source_tree_sha256={before['tree_sha256']}")
    print(f"PASS published_numeric_checks={report['published_numeric_checks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
