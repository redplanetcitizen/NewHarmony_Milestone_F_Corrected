from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .accounting import load_crosswalk, read_rows, signal


METHOD = "intensita_fisica_2012_riscalata_per_rapporto_di_attivita_reale_2019"
THRESHOLDS = {"green_max": 1.02, "yellow_max": 1.05, "orange_max": 1.10}


def _as_optional_float(value: str | None) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    return float(value)


def compute_physical_accounts(
    sector_rows: list[dict],
    coefficient_path: Path,
    baseline_path: Path,
    crosswalk_path: Path,
) -> tuple[list[dict], list[dict]]:
    """Calcola masse dirette senza moltiplicare importi espressi in anni-prezzo diversi.

    Ogni coefficiente (kg per milione di USD 2012) viene prima applicato all'output
    osservato 2012 dello stesso settore ecologico. La massa di base così ottenuta è
    poi scalata con il rapporto tra output pianificato e output osservato 2019 del
    corrispondente settore F, entrambi espressi a prezzi reali 2019.
    """
    coefficient_rows = read_rows(coefficient_path)
    coefficients = {row["ID"]: row for row in coefficient_rows}
    baseline = {
        row["ID"]: float(row["output_2012_million_usd"])
        for row in read_rows(baseline_path)
    }
    pollutants = [name for name in coefficient_rows[0] if name not in {"ID", "Settore"}]
    expected_codes = {row["bea_code"] for row in sector_rows}
    crosswalk = load_crosswalk(crosswalk_path, expected_codes)

    published = {
        (row["technology_mode"], int(row["year"])): int(row["published"])
        for row in sector_rows
    }
    totals: dict[tuple[str, int, str], float] = defaultdict(float)
    contributions: list[dict] = []

    for row in sector_rows:
        mode = row["technology_mode"]
        year = int(row["year"])
        code = row["bea_code"]
        observed_2019 = float(row.get("observed_gross_output_2019_real_musd") or 0.0)
        activity_ratio = (
            float(row["gross_output_real_musd"]) / observed_2019
            if observed_2019 > 0 else 0.0
        )
        mappings = [item for item in crosswalk[code] if item["mapping_status"] == "mapped"]
        for pollutant in pollutants:
            values: list[float] = []
            for mapping in mappings:
                coefficient = _as_optional_float(coefficients[mapping["eco_id"]].get(pollutant))
                if coefficient is not None:
                    values.append(coefficient * baseline[mapping["eco_id"]] * activity_ratio)
            if not values:
                continue
            value = sum(values)
            totals[(mode, year, pollutant)] += value
            contributions.append(
                {
                    "technology_mode": mode,
                    "year": year,
                    "published": published[(mode, year)],
                    "pollutant": pollutant,
                    "bea_code": code,
                    "sector_name": row["sector_name"],
                    "value_kg": value,
                    "unit": "kg",
                    "activity_ratio_to_observed_2019": activity_ratio,
                    "coefficient_coverage": "complete" if len(values) == len(mappings) else "partial",
                    "signal": "n.d.",
                    "signal_reason": "nessuna soglia settoriale documentata; intensita costante",
                    "accounting_method": METHOD,
                }
            )

    modes = sorted({row["technology_mode"] for row in sector_rows})
    years_by_mode = {
        mode: sorted({int(row["year"]) for row in sector_rows if row["technology_mode"] == mode})
        for mode in modes
    }
    baselines = {
        (mode, pollutant): totals[(mode, years_by_mode[mode][0], pollutant)]
        for mode in modes for pollutant in pollutants
    }
    available_keys = {
        (item["technology_mode"], item["year"], item["pollutant"])
        for item in contributions
    }
    summary: list[dict] = []
    for mode in modes:
        for year in years_by_mode[mode]:
            for pollutant in pollutants:
                value = totals[(mode, year, pollutant)]
                base = baselines[(mode, pollutant)]
                available = (mode, year, pollutant) in available_keys
                ratio = value / base if available and base > 0 else None
                summary.append(
                    {
                        "technology_mode": mode,
                        "year": year,
                        "published": published[(mode, year)],
                        "pollutant": pollutant,
                        "value_kg": value if available else None,
                        "unit": "kg",
                        "index_2019_100": 100.0 * ratio if ratio is not None else None,
                        "ratio_to_2019": ratio,
                        "signal": signal(ratio, THRESHOLDS) if ratio is not None else "n.d.",
                        "signal_interpretation": "pressione aggregata relativa al 2019; non pericolosita",
                        "accounting_method": METHOD,
                    }
                )
    return summary, contributions
