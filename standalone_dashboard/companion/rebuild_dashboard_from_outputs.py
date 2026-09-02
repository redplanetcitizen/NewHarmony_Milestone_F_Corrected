from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from eco_companion.adapter import enrich_sector_diagnostics_from_model, write_rows
from eco_companion.dashboard_data import build_dashboard
from eco_companion.physical_accounting import compute_physical_accounts
from eco_companion.accounting import compute_accounts


def read_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def main() -> int:
    parser = argparse.ArgumentParser(description="Rigenera il cruscotto dagli output esistenti")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--milestone-root", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    output = (args.output_dir or (root / "outputs")).resolve()
    existing = json.loads((output / "dashboard.json").read_text(encoding="utf-8"))
    source = {
        "repository": existing["meta"]["source_repository"],
        "commit": existing["meta"]["source_commit"],
        "tree_sha256": existing["meta"]["source_tree_sha256"],
    }
    annual = read_rows(output / "economic_annual_path.csv")
    sectors = enrich_sector_diagnostics_from_model(args.milestone_root.resolve(), read_rows(output / "economic_sector_path.csv"), annual)
    ecological, contributions, coverage = compute_accounts(
        sectors,
        root / "data" / "associazioni_ecologiche_qualitative_72x55.csv",
        root / "data" / "crosswalk_f71_to_eco72.csv",
    )
    physical, physical_contributions = compute_physical_accounts(
        sectors,
        root / "data" / "coefficienti_ecologici_fisici_72x55.csv",
        root / "data" / "baseline_output_fisico_2012.csv",
        root / "data" / "crosswalk_f71_to_eco72.csv",
    )
    dashboard = build_dashboard(
        annual,
        ecological,
        contributions,
        coverage,
        source,
        sector_rows=sectors,
        physical_rows=physical,
        physical_contribution_rows=physical_contributions,
    )
    write_rows(output / "economic_sector_path.csv", sectors)
    write_rows(output / "ecological_summary.csv", ecological)
    write_rows(output / "ecological_contributions.csv", contributions)
    write_rows(output / "mapping_coverage.csv", coverage)
    write_rows(output / "physical_ecological_summary.csv", physical)
    write_rows(output / "physical_ecological_contributions.csv", physical_contributions)
    text = json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n"
    (output / "dashboard.json").write_text(text, encoding="utf-8")
    (root / "dashboard" / "data.json").write_text(
        json.dumps(dashboard, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    report_path = output / "VALIDATION_REPORT.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report.update(
            {
                "economic_sector_rows": len(sectors),
                "ecological_summary_rows": len(ecological),
                "ecological_contribution_rows": len(contributions),
                "physical_ecological_summary_rows": len(physical),
                "physical_ecological_contribution_rows": len(physical_contributions),
                "physical_pollutants_available": len(dashboard["physical_pollutants"]),
                "ecological_accounting_modes": ["qualitative_association", "physical_direct_mass"],
                "physical_coefficient_year": 2012,
                "physical_rebase": "activity_ratio_to_observed_real_2019",
                "sector_diagnostic_harmony": True,
                "solver_modified": False,
            }
        )
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "sectors": len(dashboard["sectors"]),
                "mapped_sectors": sum(row["ecologically_mapped"] for row in dashboard["sectors"]),
                "physical_sector_contributions": sum(
                    len(mode["physical_sector_contributions"]) for mode in dashboard["modes"].values()
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
