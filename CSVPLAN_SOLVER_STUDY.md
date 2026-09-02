# Deep-Dive Study: `csvplan-corrected` — `legacy` vs `reconciled` vs `solver`

This document is a study aid for understanding, and communicating the limits
and results of, the three greedy-heuristic implementations that live inside
the `csvplan-corrected` repository (`redplanetcitizen/csvplan-corrected`):
`csvplan_corrected/legacy.py`, `csvplan_corrected/reconciled.py`, and
`csvplan_corrected/solver.py`. All findings below come from reading the
source in full and from empirical runs on the package's own default dataset
(`data/jeu*.csv` — 5 sectors: Agriculture, Industry, Construction, Services,
Foreign Trade; 5-year published horizon).

**Why three modules, not one.** Their own docstrings state the intent
precisely, and it matters for interpreting every number below:

- `legacy.py`: *"Legacy compatibility implementation of `csvplan.jl`... This
  module is intentionally autonomous and preserves the Julia prototype's
  runtime semantics on the supplied CSV files, including its anomalous linear
  indexing, terminal buffer, investment scheduling, depreciation timing,
  Harmony calculation, and sample standard deviation."* It is a **byte-faithful
  behavioral replica** of the original Julia prototype, defects included.
- `reconciled.py`: *"the implementation target fixed by the completed
  source/code adjudication... intentionally distinct from... `legacy`, the
  numerical replay of Cockshott's historical prototype... The default
  reference demonstration deliberately retains the historical 70% preliminary
  replacement schedule... and first-blocked stopping rule."* It fixes some
  confirmed numerical defects but **keeps the investment floor and a
  single-candidate destination policy on purpose**, as an audited historical
  reproduction, not as the package's best available engine.
- `solver.py`: *"Corrected matrix implementation of Cockshott's New Harmony
  design. This module deliberately does not reproduce the numerical output of
  `csvplan.jl`. It retains the Julia prototype's useful matrix/tensor model
  while enforcing the accounting and intertemporal constraints stated in
  `Design for Julia implementation of the New Harmony algorithm`."* A
  **ground-up rebuild** from the 2020 Design PDF, independent of `legacy.py`'s
  data structures, with no investment floor at all.

---

## 1. Architecture map

```
legacy.py  ──(Scenario/PlanProblem data model, Harmony/depreciation primitives)──▶  reused by
                                                                                      │
                                                                                      ▼
                                                                              reconciled.py
                                                                    (own search loop: _attempt_destination,
                                                                     _ordered_destinations, _build_initial;
                                                                     own corrected output/harmony refresh:
                                                                     _refresh_outputs, _refresh_harmony)

solver.py  ──(own PlanProblem/Scenario, own read_problem, own harmony/propagate_stock)──▶  fully independent
                                                                    (_candidate_for_destination, terminal_replacement,
                                                                     max_consumption_scale, validate_scenario)
```

`legacy.py` and `reconciled.py` share one data model (`legacy.Scenario`,
`legacy.PlanProblem`); `solver.py` defines its own, structurally different,
`Scenario`/`PlanProblem`. **The three are not drop-in interchangeable** —
`reconciled.py` imports and extends `legacy.py`; `solver.py` shares no code
with either beyond the CSV-reading pattern.

---

## 2. Mechanism-by-mechanism comparison

| Mechanism | `legacy.py` (`solvePlanProblem`) | `reconciled.py` (`solve_problem`, default config) | `solver.py` (`solve_problem`) |
|---|---|---|---|
| Initial investment | `INITIAL_INVESTMENT_LEVEL=0.7` × (caps×dep), every year but the last (line 723) | same 0.7 floor, explicitly retained as `warm_start_level` (line 57, 295) | **zero** — `investments = np.zeros(...)` (line 528) |
| Destination selection | **fixed loop order** `for i in range(1, TheLastYear)`, accepts first `i` with `h[i] < meanh` (lines 757, 782-783) — this is the exact same fixed-order defect found earlier in `csvplan.jl` | worst-first via `np.argsort(s.h)`, but `historical_first_blocked` (default) takes **only the single worst year** (`order[:1]`) and **stops the entire run** if it fails (lines 390-396, 463-465) | worst-first **re-ranked every iteration** over the **full** eligible list (line 546); tries each until one yields *any* improving move |
| Target level | `harmonyInverse(meanh)`, but only used implicitly through a fixed `EPSILON=0.25/14` step (`legacy.Estimate_how_much__production_to_be_scaled_up`) | `harmonyInverse(scenario.meanh)` × resolved epsilon (0.25/14 by default) — `_attempt_destination`, line 346-348 | `harmony_inverse(scenario.meanh)` compared against current, scaled by an **adaptive** step (`_candidate_for_destination`, line 481-486) |
| Source-year valuation | **full re-simulation** per candidate source year: `gainfromInvesting`→`variant_scenario`→`update_outputs`→`computeHarmonies` (lines 336-354) — the same expensive path found in `csvplan.jl` | full re-simulation per candidate (`_candidate`→`_refresh`, line 317-332) | full re-simulation per candidate (`_evaluate`, called from `_candidate_for_destination`, line 503) — **not** the cheap analytic shortcut `harmony2.jl`/E+1 use |
| Depreciation-aware sourcing | `inversedepreciate`, recursive, single scalar horizon-implied factor (line 145-149) | `_inverse_for_destination`, closed-form `(1-dep)^periods` (line 182-194) | `inverse_depreciate`, closed-form `(1-dep)^exponent` (line 221-232) — same formula as `reconciled.py`'s |
| Terminal year | one-shot target rescale before the search starts (`For_the_last_year_of_the_plan_return_a_net_output_target`, applied once, line 715-718); no re-solve during search | same one-shot pre-search rescale (`_build_initial`, line 266-273); no re-solve during search | **re-solved on every evaluation** via `terminal_replacement`, `x=(I-A-D)^-1(q·g)` with `q=min(labour,capital)` bound (line 297-332, called inside `_evaluate`) |
| Step size | fixed `EPSILON=0.25/14≈0.0179` | fixed, policy-selectable (`historical_matrix`=0.25/14, or `text_first_suggestion`=1/(H+1)) | **adaptive**: grows ×1.15 on a clean accepted move, shrinks ×0.5 on detected oscillation or on no candidate found, bounded in [1e-5, 0.5] (lines 106-110, 585-590) |
| Acceptance gate | accepts if `gain > 0` and all of the source year's net outputs stay `> 0` (line 378) | accepts if `candidate.meanh > scenario.meanh + tol` (line 502) | accepts if `candidate.objective > scenario.objective + tol` (line 506), where `objective = Σ annual_harmony` — a full-horizon sum, not just the mean |
| Constraint/feasibility audit | none beyond the source-year positivity check above | `negative_net_output_cells` counted and reported, but **not enforced** during search | `validate_scenario`/`YearConstraintReport` — explicit flow-balance, labour, capital, and consumption compliance check available (`strict` mode raises) |

---

## 3. Known limits of each engine, evidenced

**`legacy.py`** — carries forward, faithfully and by design, both regressions
already identified in `csvplan.jl` itself:
1. Fixed loop-order destination selection, not true worst-first.
2. Full-resimulation source valuation (no analytic shortcut).

New finding from this study, using the package's own comparison utility
(`solver.compare_with_legacy`, see §4): **`legacy_negative_outputs_hidden =
True`** on the default dataset — the historically-faithful engine's accepted
final scenario contains product/year cells with **actual negative net
output** that its own acceptance logic does not catch (it only checks the
*source* year's positivity, per §2, not the destination's). This is a
correctness defect in the original algorithm, not a stylistic difference —
faithfully reproduced here on purpose, to make it auditable.

**`reconciled.py`** — fixes the accounting defects it documents (labeled
`C02`, `C13`, `C26`, `C28` in its provenance metadata, referencing
`CSVPLAN_ADJUDICATION_STATUS.md`, a file in the `csvplan-corrected` repo not
yet reviewed for this study), but under its **default configuration**:
- Retains the 0.7 investment floor as a deliberate historical-fidelity
  choice, not a numerical necessity (its own docstring says so explicitly).
- `historical_first_blocked` considers only the single worst-ranked year per
  outer pass and **terminates the entire run** the moment that one year has
  no improving move — even if other, less-bad years still have room to
  improve. This is documented as a `historical_matrix_specialization`, i.e.
  a deliberate replica of the original's behavior, not a requirement.
- The alternative `ranked_full_pass` policy removes that restriction, but
  earlier testing (this conversation, prior turn) showed that lowering
  `warm_start_level` under `ranked_full_pass` **without** also adopting
  `solver.py`'s other mechanisms (adaptive step, per-iteration terminal
  re-solve, full-objective acceptance) degrades results monotonically and
  collapses below `warm_start_level≈0.3`.

**`solver.py`** — no floor, and empirically the strongest of the three (§4),
but with one open item:
- `terminal_capital_limited = True` on the default dataset: the terminal
  year's capital-constrained output scale (`q_capital`) binds before the
  labour-constrained scale (`q_labour`), so full employment is not reached in
  the final year of the accepted scenario. Because `terminal_replacement` is
  re-solved on **every** evaluation (not just once, unlike the other two
  engines), this is a live, continuously-recomputed diagnostic, not a stale
  pre-search estimate — which makes it a substantive finding about capital
  adequacy on this dataset. Whether it reflects a genuine capital shortfall
  in the `jeu*` test economy or a searchable improvement is not yet
  determined and would require targeted investigation (e.g., checking
  whether any feasible investment schedule under this data closes the gap).

---

## 4. Empirical results (this dataset: 5 sectors × 5 years, `data/jeu*.csv`)

All runs isolated in separate subprocesses to avoid cross-import
contamination between engines; repeated twice each; identical results both
times (all three engines are deterministic).

| | `legacy.solvePlanProblem` | `reconciled.solve_problem` (default) | `solver.solve_problem` |
|---|---|---|---|
| mean harmony | 0.4782 | 0.4938 | **0.5045** |
| iterations | **811** | 42 attempts / 41 accepted | 69 |
| investment floor | 0.7 | 0.7 | 0 |
| negative net output present | **yes, unflagged** (`legacy_negative_outputs_hidden=True`) | 0 cells (checked, not enforced) | not directly comparable metric; `validate_scenario` available |
| wall time (isolated) | not separately measured this pass | ~0.60 s | ~0.15 s |
| peak RSS | not separately measured this pass | ~29.5 MB | ~28.9 MB |

Source for the `legacy` row: `solver.run_default_with_legacy_comparison()`,
the comparison utility built into the package itself (`solver.py`,
`compare_with_legacy`), run directly rather than re-derived:

```
years_compared: 5
corrected_mean_harmony: 0.5045277466941249
legacy_mean_harmony:    0.4782416734493745
corrected_iterations:   69
legacy_iterations:      811
max_abs_net_output_difference: 1058165.77   (scale-dependent; jeu* values are ~1e5-1e6)
legacy_negative_outputs_hidden: True
```

**Reading it together**: the historically-faithful engine (`legacy`), even
with the 70% floor giving it a head start, needs **~12× more iterations**
than the floor-free `solver.py`, converges to a **lower** mean harmony, and
its accepted result **hides a genuine infeasibility** (negative net output)
that its own logic never checks for at the destination year. This is a much
stronger statement than "the floor is a crutch for a weak search" — the
original search mechanics have a real correctness gap independent of the
floor.

---

## 5. Terminology map (for consistent communication across sources)

| Concept | `legacy.py` / `reconciled.py` | `solver.py` | E+1 Final (`e_corrected.py`) |
|---|---|---|---|
| per-year harmony | `s.h` | `scenario.h` | `current.feasible_ratio` → harmony via `c.harmony` |
| mean harmony | `s.meanh` | `scenario.meanh` | `current.mean_harmony` |
| target fulfillment level | `harmonyInverse(meanh)` | `harmony_inverse(scenario.meanh)` | `c.harmony_inverse(current.mean_harmony)` |
| capital stock trajectory | `s.si` | `scenario.S` | (inside `CorrectedScenario`, via `e_corrected`) |
| investment tensor | `s.investments` | `scenario.I` | `scenario.investments` |
| depreciation-aware sourcing | `inversedepreciate` | `inverse_depreciate` | `inverse_depreciate_gap` |
| full re-evaluation | `update_outputs`+`computeHarmonies` | `_evaluate` | `ec.evaluate` |
| investment floor constant | `INITIAL_INVESTMENT_LEVEL=0.7` | none | none |

---

## 6. Open items for further study

1. Read `CSVPLAN_ADJUDICATION_STATUS.md` in `csvplan-corrected` to attach
   precise descriptions to the `C02`/`C13`/`C26`/`C28` defect codes cited in
   `reconciled.py`'s provenance metadata — currently only their *names* are
   known from code comments, not the audit's full reasoning.
2. Determine whether `solver.py`'s `terminal_capital_limited=True` reflects
   an intrinsic capital shortfall in the `jeu*` dataset or a gap the search
   could still close with a different acceptance/step policy.
3. `solver.py`'s destination loop still accepts the **first** improving
   destination found in worst-first order (`break` at line 558) rather than
   the globally best move across all eligible destinations at the current
   step, unlike E+1 Final's approach — not yet tested whether closing this
   gap changes the result materially on this dataset.
