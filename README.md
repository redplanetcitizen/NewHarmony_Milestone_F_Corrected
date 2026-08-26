# New Harmony — Milestone F Corrected

Milestone F Corrected is a controlled extension of Milestone E Corrected. It replaces the obsolete E baseline used by the original F package and verifies the final multiperiod solution against the corrected annual accounting identities.

Neither predecessor is modified. `reference/` contains both the legacy Milestone E archive and the autonomous Milestone E Corrected archive.

## Csvplan reconciliation status

The source/code audit of `csvplan.jl` and the subsequent Milestone E alignment do **not** require a numerical change to the final F solver. F already inherits the reconciled physical core where that core remains meaningful under simultaneous optimization: vector accounting, exact stock timing, investment-cohort depreciation and full feasibility checks.

F's simultaneous lexicographic LP, effective capital bundle, asset-source restriction, Harmony approximation, historical dynamic `C_t` and three-year shadow boundary are explicit Milestone F research extensions. They are not presented as recovered Cockshott rules. The detailed mapping is in `CSVPLAN_RECONCILED_ALIGNMENT.md`; machine-readable provenance is in `code/csvplan_reconciled_alignment.py`.

Final F also has no iterative warm-start state. It does not impose the historical `csvplan.jl` 70% preliminary schedule, but this is not described as a theoretically privileged `0% warm start`: investment is an endogenous nonnegative LP decision variable.

## Experimental sequence

1. **E Corrected baseline.** The accepted corrected numerical solver is replayed with its terminal equation, endogenous marginal investment, exact flow accounting and complete constraint checks. Its embedded solver blob is identical to the numerical E solver used by the aligned E branch.
2. **Legacy E+1 diagnostic.** The original development proposal mechanism is retained only to document the historical development path. It is explicitly excluded from the corrected baseline.
3. **E+2 — forward-looking capital control.** The five-year problem is solved simultaneously with cell-level capital constraints and the lexicographic max-min/Harmony/investment objective.
4. **E+3 — dynamic/effective capital.** The empirical capital representation is changed to a user-sector bundle and new investment is restricted to asset-bearing source sectors. Historical mode remains an ex-post diagnostic.
5. **F Corrected — 5+3 horizon.** Three stationary shadow years value post-2023 capacity. The final computational-year investment is zero because it cannot become productive inside the horizon.

## Final headline results

| Mode | E Corrected min fulfillment | F Corrected min fulfillment | E Corrected mean Harmony | F Corrected mean Harmony | E Corrected investment / BEA | F Corrected investment / BEA | E Corrected 2023 stock / BEA | F Corrected 2023 stock / BEA |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen | 0.6244 | **0.8988** | 0.4196 | **0.4500** | 26.88% | **71.83%** | 78.74% | **91.26%** |
| Historical | 0.6305 | **0.9673** | 0.4195 | **0.4679** | 27.47% | **70.88%** | 78.86% | **91.47%** |

Cumulative modeled gross output rises from 70.19% to 86.58% of BEA in Frozen mode and from 70.75% to 92.53% in Historical mode.

Observed BEA investment remains diagnostic: it is neither an objective nor a lower bound. No 70% preliminary schedule is present. The approximately 71% investment ratios produced by final F are endogenous outcomes, not imposed replacement percentages.

## Important interpretation

F is not a pure replay of the original `csvplan` heuristic or of `reconciled.py`. From E+2 onward it is a hybrid lexicographic New Harmony planner. Leontief technology, capital accumulation, depreciation and Harmony are retained, but full-horizon feasibility first maximizes the worst target fulfillment.

The E Corrected terminal equation is not added to final F. F already uses three stationary shadow years as its boundary treatment; applying both mechanisms would double count the terminal requirement. Every solved F year is instead audited for flow balance, exact stock recurrence, capital, labour, imports, nonnegative net output and nonnegative investment.

The Historical dynamic `C_t` benchmark is diagnostic/ex-post. It must not be interpreted as information that a planner in 2019 could know. A prospective application would forecast or update capital productivity recursively as new observations become available.

## Key files

- `code/new_harmony_empirical_f.py` — unchanged numerical Milestone F implementation and all variant runs.
- `code/new_harmony_empirical_e_corrected.py` — embedded corrected E numerical baseline.
- `code/csvplan_reconciled_alignment.py` — machine-readable source/core versus F-extension provenance contract.
- `CSVPLAN_RECONCILED_ALIGNMENT.md` — rule-by-rule reconciliation matrix.
- `PROVENANCE.md` — pinned dependency checkpoints and provenance summary.
- `results/VARIANT_COMPARISON.csv` — corrected E baseline, separated legacy diagnostic and F variants.
- `results/VARIANT_ANNUAL.csv` — annual fulfillment, Harmony, investment, stock and gross output.
- `results/OUTPUT_AGGREGATE_COMPARISON.csv` — five-year gross-output comparison with BEA.
- `results/F_FINAL_SUMMARY.csv` — final F headline rows.
- `results/F_final/{frozen,historical}/annual_path.csv` — detailed final paths including the three shadow years.
- `results/F_final/{frozen,historical}/constraint_audit.csv` — corrected annual accounting and feasibility audit.
- `CORRECTIONS_AUDIT.md` — disposition of inherited rules and F-specific extensions.
- `reference/NewHarmony_Milestone_E_Corrected.zip` — accepted corrected predecessor.
- `reference/NewHarmony_Milestone_E.zip` — preserved legacy predecessor.
