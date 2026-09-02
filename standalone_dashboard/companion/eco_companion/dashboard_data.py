from __future__ import annotations

from collections import defaultdict


def build_dashboard(
    annual_rows: list[dict],
    qualitative_rows: list[dict],
    association_rows: list[dict],
    coverage_rows: list[dict],
    source: dict,
    sector_rows: list[dict] | None = None,
    physical_rows: list[dict] | None = None,
    physical_contribution_rows: list[dict] | None = None,
) -> dict:
    sector_rows = sector_rows or []
    physical_rows = physical_rows or []
    physical_contribution_rows = physical_contribution_rows or []
    pollutants = sorted({row["pollutant"] for row in qualitative_rows} | {row["pollutant"] for row in physical_rows})
    physical_pollutants = sorted({
        row["pollutant"] for row in physical_rows
        if row.get("value_kg") not in (None, "")
    })
    mapped_sector_names = {row["sector_name"] for row in association_rows}
    sector_catalogue = sorted(
        {
            (int(row["sector_index"]), row["bea_code"], row["sector_name"])
            for row in sector_rows
        },
        key=lambda item: item[2],
    )

    physical_grouped: dict[tuple[str, int, str], list[dict]] = defaultdict(list)
    for row in physical_contribution_rows:
        physical_grouped[(row["technology_mode"], int(row["year"]), row["pollutant"])].append(row)

    modes = {}
    for mode in sorted({row["technology_mode"] for row in annual_rows}):
        annual = sorted(
            [row for row in annual_rows if row["technology_mode"] == mode],
            key=lambda row: int(row["year"]),
        )
        qualitative = sorted(
            [row for row in qualitative_rows if row["technology_mode"] == mode],
            key=lambda row: (int(row["year"]), row["pollutant"]),
        )
        associations = sorted(
            [row for row in association_rows if row["technology_mode"] == mode],
            key=lambda row: (int(row["year"]), row["sector_name"], row["pollutant"]),
        )
        physical = sorted(
            [row for row in physical_rows if row["technology_mode"] == mode],
            key=lambda row: (int(row["year"]), row["pollutant"]),
        )
        physical_contributions = sorted(
            [row for row in physical_contribution_rows if row["technology_mode"] == mode],
            key=lambda row: (int(row["year"]), row["sector_name"], row["pollutant"]),
        )
        coverage = sorted(
            [row for row in coverage_rows if row["technology_mode"] == mode],
            key=lambda row: int(row["year"]),
        )
        sector_economy = sorted(
            [row for row in sector_rows if row["technology_mode"] == mode],
            key=lambda row: (int(row["year"]), row["sector_name"]),
        )
        top = {}
        for row in physical:
            key = (mode, int(row["year"]), row["pollutant"])
            top[f"{row['year']}|{row['pollutant']}"] = sorted(
                physical_grouped.get(key, []),
                key=lambda item: float(item["value_kg"]),
                reverse=True,
            )[:10]
        modes[mode] = {
            "annual": annual,
            "coverage": coverage,
            "sector_economy": sector_economy,
            "qualitative_summary": qualitative,
            "qualitative_associations": associations,
            "physical_ecological": physical,
            "physical_sector_contributions": physical_contributions,
            "physical_top_sectors": top,
        }

    return {
        "meta": {
            "title": "Milestone F Corrected — Contabilità ecologica ex post",
            "source_repository": source["repository"],
            "source_commit": source["commit"],
            "source_tree_sha256": source["tree_sha256"],
            "solver_modified": False,
            "physical_method": "Coefficienti diretti kg/MUSD 2012 applicati alla massa di base 2012 e riscalati con il rapporto di attività reale pianificata/osservata 2019.",
            "qualitative_interpretation": "0/1/2 sono categorie di associazione: nessuna, operativa, caratteristica. Non sono quantità né livelli di pericolo.",
            "sector_harmony_interpretation": "Indicatore diagnostico H(r)=r/(1,1+r), con r pari a output lordo realizzato / fabbisogno lordo sociale e di investimento. Non è una variabile autonoma del solver.",
            "traffic_light_interpretation": "Il semaforo fisico aggregato indica la variazione rispetto al 2019. Per il singolo settore resta n.d. finché non esistono soglie documentate o intensità temporali specifiche.",
        },
        "pollutants": pollutants,
        "physical_pollutants": physical_pollutants,
        "sectors": [
            {
                "sector_index": index,
                "bea_code": code,
                "sector_name": name,
                "ecologically_mapped": name in mapped_sector_names,
            }
            for index, code, name in sector_catalogue
        ],
        "modes": modes,
    }
