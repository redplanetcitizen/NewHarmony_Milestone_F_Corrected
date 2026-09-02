from __future__ import annotations

import csv
import importlib
import sys
from contextlib import contextmanager
from pathlib import Path


DIAGNOSTIC_BASIS = "copertura_del_fabbisogno_lordo_sociale_e_di_investimento"


@contextmanager
def milestone_modules(root: Path):
    """Importa il solver originale senza produrre bytecode nella sua cartella."""
    code_dir = str((root / "code").resolve())
    old_dont_write = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.path.insert(0, code_dir)
    try:
        c = importlib.import_module("new_harmony_empirical_c")
        d = importlib.import_module("new_harmony_empirical_d")
        f = importlib.import_module("new_harmony_empirical_f")
        yield c, d, f
    finally:
        if sys.path and sys.path[0] == code_dir:
            sys.path.pop(0)
        sys.dont_write_bytecode = old_dont_write


def solve_final_paths(root: Path, modes: tuple[str, ...]) -> tuple[list[dict], list[dict]]:
    sector_rows: list[dict] = []
    annual_rows: list[dict] = []
    with milestone_modules(root) as (c, d, f):
        for mode in modes:
            data5 = c.load_model_data(root / "data", mode)
            trade5 = d.load_trade_inventory(data5, root / "data")
            data8, trade8 = f.extend_with_shadows(data5, trade5, 3)
            result = f.solve_lexicographic_lp(
                data8,
                trade8,
                label="F_corrected_5plus3_shadow",
                cap_mode="sector_bundle",
                dynamic_historical_C=True,
                published_years=5,
                restrict_asset_sources=True,
            )
            for t, year in enumerate(result.years):
                gross_social_target = data8.L_by_year[t] @ data8.goals[t]
                gross_investment_requirement = data8.L_by_year[t] @ result.p[t]
                gross_requirement_target = gross_social_target + gross_investment_requirement
                annual_rows.append(
                    {
                        "technology_mode": mode,
                        "year": int(year),
                        "published": int(t < result.published_years),
                        "fulfillment": float(result.f[t]),
                        "harmony": float(c.harmony(result.f[t])),
                        "investment_real_musd": float(result.investments[t].sum()),
                        "stock_start_real_musd": float(result.stock_start[t].sum()),
                        "stock_end_real_musd": float(result.stock_end[t].sum()),
                        "gross_realized_real_musd": float(result.gross_realized[t].sum()),
                    }
                )
                for j, code in enumerate(data8.sectors):
                    gross_target = float(gross_requirement_target[j])
                    coverage = (
                        float(result.gross_realized[t, j]) / gross_target
                        if gross_target > 0 else None
                    )
                    sector_rows.append(
                        {
                            "technology_mode": mode,
                            "year": int(year),
                            "published": int(t < result.published_years),
                            "sector_index": j,
                            "bea_code": code,
                            "sector_name": data8.names[code],
                            "gross_output_real_musd": float(result.gross_realized[t, j]),
                            "observed_gross_output_2019_real_musd": float(data8.observed_gross[2019][j]),
                            "gross_social_target_real_musd": float(gross_social_target[j]),
                            "gross_investment_requirement_real_musd": float(gross_investment_requirement[j]),
                            "gross_requirement_target_real_musd": gross_target,
                            "gross_requirement_coverage": coverage,
                            "diagnostic_sector_harmony": float(c.harmony(coverage)) if coverage is not None else None,
                            "annual_plan_fulfillment": float(result.f[t]),
                            "annual_plan_harmony": float(c.harmony(result.f[t])),
                            "diagnostic_basis": DIAGNOSTIC_BASIS,
                        }
                    )
    return sector_rows, annual_rows


@contextmanager
def milestone_core_module(root: Path):
    """Carica solo il nucleo dati; non richiede SciPy né esegue il solver."""
    code_dir = str((root / "code").resolve())
    old_dont_write = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.path.insert(0, code_dir)
    try:
        yield importlib.import_module("new_harmony_empirical_c")
    finally:
        if sys.path and sys.path[0] == code_dir:
            sys.path.pop(0)
        sys.dont_write_bytecode = old_dont_write


def enrich_sector_diagnostics_from_model(
    root: Path,
    sector_rows: list[dict],
    annual_rows: list[dict],
) -> list[dict]:
    """Ricostruisce gli indicatori diagnostici da output F già validati.

    L'identità del modello è x = f·L·g + L·p. Da x, f, L e g si ricava
    esattamente il fabbisogno lordo di investimento L·p senza rieseguire il LP.
    """
    annual = {
        (row["technology_mode"], int(row["year"])): row
        for row in annual_rows
    }
    by_mode: dict[str, list[dict]] = {}
    for row in sector_rows:
        by_mode.setdefault(row["technology_mode"], []).append(row)

    enriched: list[dict] = []
    with milestone_core_module(root) as c:
        for mode, rows in by_mode.items():
            data = c.load_model_data(root / "data", mode)
            sector_index = {code: index for index, code in enumerate(data.sectors)}
            for original in rows:
                row = dict(original)
                year = int(row["year"])
                t = min(max(year - data.years[0], 0), len(data.years) - 1)
                j = sector_index[row["bea_code"]]
                fulfillment = float(annual[(mode, year)]["fulfillment"])
                gross_social = float((data.L_by_year[t] @ data.goals[t])[j])
                gross_realized = float(row["gross_output_real_musd"])
                gross_investment = gross_realized - fulfillment * gross_social
                if -1e-7 < gross_investment < 0:
                    gross_investment = 0.0
                gross_target = gross_social + gross_investment
                coverage = gross_realized / gross_target if gross_target > 0 else None
                row.update(
                    {
                        "observed_gross_output_2019_real_musd": float(data.observed_gross[2019][j]),
                        "gross_social_target_real_musd": gross_social,
                        "gross_investment_requirement_real_musd": gross_investment,
                        "gross_requirement_target_real_musd": gross_target,
                        "gross_requirement_coverage": coverage,
                        "diagnostic_sector_harmony": float(c.harmony(coverage)) if coverage is not None else None,
                        "annual_plan_fulfillment": fulfillment,
                        "annual_plan_harmony": float(c.harmony(fulfillment)),
                        "diagnostic_basis": DIAGNOSTIC_BASIS,
                    }
                )
                enriched.append(row)
    return enriched


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
