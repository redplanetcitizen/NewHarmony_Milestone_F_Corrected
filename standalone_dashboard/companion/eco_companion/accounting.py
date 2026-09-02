from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


def read_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def signal(ratio: float, thresholds: dict[str, float]) -> str:
    if ratio <= thresholds["green_max"]:
        return "verde"
    if ratio <= thresholds["yellow_max"]:
        return "giallo"
    if ratio <= thresholds["orange_max"]:
        return "arancione"
    return "rosso"


def load_crosswalk(path: Path, expected_codes: set[str]) -> dict[str, list[dict]]:
    rows = read_rows(path)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        row["allocation_share"] = float(row["allocation_share"] or 0.0)
        grouped[row["f_bea_code"]].append(row)
    missing = sorted(expected_codes - set(grouped))
    extra = sorted(set(grouped) - expected_codes)
    if missing or extra:
        raise ValueError(f"Raccordo non coerente; mancanti={missing}, extra={extra}")
    for code, mappings in grouped.items():
        active = [row for row in mappings if row["mapping_status"] == "mapped"]
        if active and abs(sum(row["allocation_share"] for row in active) - 1.0) > 1e-9:
            raise ValueError(f"Le quote di {code} non sommano a uno")
        if not active and not all(row["mapping_status"] == "unmapped" for row in mappings):
            raise ValueError(f"Stato di raccordo non valido per {code}")
    return grouped


ASSOCIATION_LABELS = {0: "nessuna", 1: "operativa", 2: "caratteristica"}


def compute_accounts(
    sector_rows: list[dict],
    association_path: Path,
    crosswalk_path: Path,
    thresholds: dict[str, float] | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    thresholds = thresholds or {"green_max": 1.02, "yellow_max": 1.05, "orange_max": 1.10}
    associations = read_rows(association_path)
    association_by_id = {row["ID"]: row for row in associations}
    pollutants = [name for name in associations[0] if name not in {"ID", "Settore"}]
    expected_codes = {row["bea_code"] for row in sector_rows}
    crosswalk = load_crosswalk(crosswalk_path, expected_codes)

    associations_by_sector: dict[tuple[str, str], int] = defaultdict(int)
    gross_total: dict[tuple[str, int], float] = defaultdict(float)
    gross_mapped: dict[tuple[str, int], float] = defaultdict(float)

    for row in sector_rows:
        mode = row["technology_mode"]
        year = int(row["year"])
        code = row["bea_code"]
        output = float(row["gross_output_real_musd"])
        gross_total[(mode, year)] += output
        mappings = [m for m in crosswalk[code] if m["mapping_status"] == "mapped"]
        if not mappings:
            continue
        gross_mapped[(mode, year)] += output
        for mapping in mappings:
            eco = association_by_id[mapping["eco_id"]]
            for pollutant in pollutants:
                level = int(float(eco[pollutant] or 0.0))
                key = (code, pollutant)
                associations_by_sector[key] = max(associations_by_sector[key], level)

    summary_rows: list[dict] = []
    years_by_mode = {
        mode: sorted({int(row["year"]) for row in sector_rows if row["technology_mode"] == mode})
        for mode in sorted({row["technology_mode"] for row in sector_rows})
    }
    for mode, years in years_by_mode.items():
        published_by_year = {
            int(row["year"]): int(row["published"])
            for row in sector_rows
            if row["technology_mode"] == mode
        }
        for year in years:
            for pollutant in pollutants:
                levels = [
                    level for (code, name), level in associations_by_sector.items()
                    if name == pollutant and level > 0
                ]
                summary_rows.append(
                    {
                        "technology_mode": mode,
                        "year": year,
                        "published": published_by_year[year],
                        "pollutant": pollutant,
                        "operational_sector_count": sum(level == 1 for level in levels),
                        "characteristic_sector_count": sum(level == 2 for level in levels),
                        "associated_sector_count": len(levels),
                        "accounting_mode": "qualitative_association",
                    }
                )

    published_lookup = {
        (row["technology_mode"], int(row["year"])): int(row["published"])
        for row in sector_rows
    }
    contribution_rows = []
    sector_identity = {
        (row["bea_code"], row["sector_name"])
        for row in sector_rows
    }
    for mode, years in years_by_mode.items():
        for year in years:
            for code, name in sorted(sector_identity):
                for pollutant in pollutants:
                    level = associations_by_sector[(code, pollutant)]
                    if level == 0:
                        continue
                    contribution_rows.append(
                        {
                            "technology_mode": mode,
                            "year": year,
                            "published": published_lookup[(mode, year)],
                            "pollutant": pollutant,
                            "bea_code": code,
                            "sector_name": name,
                            "association_level": level,
                            "association_label": ASSOCIATION_LABELS[level],
                            "accounting_mode": "qualitative_association",
                        }
                    )
    coverage_rows = []
    for mode, years in years_by_mode.items():
        for year in years:
            total = gross_total[(mode, year)]
            mapped = gross_mapped[(mode, year)]
            coverage_rows.append(
                {
                    "technology_mode": mode,
                    "year": year,
                    "gross_total_real_musd": total,
                    "gross_mapped_real_musd": mapped,
                    "coverage_ratio": mapped / total if total else 0.0,
                    "unmapped_ratio": 1.0 - mapped / total if total else 0.0,
                }
            )
    return summary_rows, contribution_rows, coverage_rows
