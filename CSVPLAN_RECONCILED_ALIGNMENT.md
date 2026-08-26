# Milestone F alignment with the reconciled csvplan reference

## Scope

This audit asks whether Milestone F Corrected must change after the source/code reconciliation completed in `redplanetcitizen/csvplan-corrected` and the provenance alignment completed for Milestone E Corrected.

Reference points:

- Milestone F pre-alignment baseline: `d71a68c6f02cde756ed814b8e209b23177ab56e0`.
- Milestone E accepted numerical baseline: `3faf1657bf0df93906477ed3ba85766406f323ba`.
- Milestone E csvplan-alignment gate: `eecbc29ec6b82a677545eca4f9540d1623328d98` on branch `align-csvplan-reconciled`.
- Embedded E solver Git blob: `193fce86af7a7497035bb3407e3ec972a8598bc2`, identical in F and in the aligned E branch.
- Reconciled csvplan implementation checkpoint: `ded576c5b8c80d2bbc9fbf3a8a7a391f0a64a433` in `redplanetcitizen/csvplan-corrected`.

The governing rule is the same as for E: source-supported accounting and capital-dynamic identities are inherited; F may replace the iterative controller with a different optimization architecture, but every such replacement must be labelled as an F extension rather than as a recovered Cockshott rule.

## Dependency matrix

| Topic | Reconciled csvplan / aligned E status | Milestone F implementation | Alignment decision |
|---|---|---|---|
| Net social output | Vector final output net of capital-goods production | LP imposes `(I-A_t)x_t = f_t g_t + p_t`, with `p_t` equal to the source-row sum of the investment tensor | **ALIGNED CORE** |
| Robust annual Harmony | Minimum across all positive-target products | F uses a common annual plan-ray factor `f_t`; every positive target component has the same fulfillment `f_t`, so robust annual Harmony is exactly `H(f_t)` within this plan-ray restriction | **ALIGNED EQUIVALENT SPECIALIZATION** |
| Stock recurrence | `S_end[t] = S_start[t]*(1-d_t) + I_t`, investment in `t` productive at start `t+1` | Reconstructed and audited annually with the same timing | **ALIGNED CORE** |
| Source-to-destination depreciation | Exact survival of earlier investment cohorts | LP capital constraints propagate each cohort with the relevant cell-specific survival factors | **ALIGNED CORE IN FORWARD FORM** |
| Candidate-state admissibility | Iterative candidates must satisfy physical constraints | F has no candidate loop; the LP feasible set directly imposes capital, labour, imports, flow and non-negativity, then the solved path is independently audited | **STRUCTURAL EQUIVALENT; ITERATIVE RULE NOT APPLICABLE** |
| Destination-year priority | Lowest-Harmony year first in the iterative controller | F solves all years simultaneously | **NOT APPLICABLE; F ARCHITECTURE EXTENSION** |
| Blocked-year fallback | E completion rule, not recovered Cockshott text | No sequential destination search exists | **NOT APPLICABLE** |
| Source-year selection | Earlier source years with positive overall-Harmony gain in the iterative controller | Investment by source year is chosen simultaneously by the LP | **NOT APPLICABLE; F ARCHITECTURE EXTENSION** |
| C26 capital increment formula | Historical matrix specialization unresolved by text; E uses actual cell gap as an empirical extension | F does not use an epsilon-sized C26 transfer; investment quantities are endogenous LP variables | **NOT APPLICABLE** |
| 70% preliminary schedule | Historical code-only warm start, not a theoretical constant | F has no iterative warm start at all. Investment variables are endogenous nonnegative LP decisions. No preliminary 70% schedule is imposed | **F ARCHITECTURE CHOICE; NOT A ZERO-WARM-START CORRECTION** |
| Epsilon / adaptive step | Numerical controller issue in iterative solvers | No epsilon or line search exists in final F | **NOT APPLICABLE** |
| CV stopping rule / max iterations | Iterative numerical controls | Final F is solved by lexicographic LP stages | **NOT APPLICABLE** |
| Objective | Reconciled iterative core accepts positive total-Harmony gains while equalizing annual Harmony | F first maximizes `theta=min_t f_t`, then approximate mean Harmony, then minimizes capital-goods production | **MILESTONE F OBJECTIVE EXTENSION** |
| Harmony optimization | Exact fractional Harmony for evaluation | Stage 2 uses an 81-point tangent upper-envelope approximation on `0<=f<=1`; reported Harmony uses the exact function | **MILESTONE F NUMERICAL EXTENSION** |
| Capital representation | Reconciled matrix witness retains source×user capital cells | Final F aggregates surviving capital into an effective bundle by user sector | **MILESTONE F EMPIRICAL EXTENSION** |
| Eligible capital-good sources | No equivalent restriction in csvplan core | New investment is restricted to selected structures/equipment/IPP-producing source sectors | **MILESTONE F EMPIRICAL EXTENSION** |
| Historical dynamic `C_t` | Not part of reconciled csvplan | Historical mode uses observed start-stock/output ratios and repeats the latest ratio into shadows | **MILESTONE F EX-POST DIAGNOSTIC** |
| Imports | Empirical E extension, absent from csvplan witness | Componentwise import envelope retained in every LP year | **INHERITED EMPIRICAL EXTENSION** |
| Inventories | E extension, absent from csvplan core | Final F does not add the E inventory-transfer search to the LP | **OMITTED E EXTENSION; NO CORE CONFLICT** |
| Terminal boundary | E terminal equation is an E boundary extension; csvplan matrix witness does not determine a unique terminal equation | F uses three stationary shadow years and fixes final-computational-year investment to zero | **MILESTONE F BOUNDARY EXTENSION** |
| Shadow continuation | Historical csvplan uses a code-only repeat-last policy with a different horizon | F repeats latest target, technology, depreciation, labour and import assumptions for exactly three years | **MILESTONE F BOUNDARY CHOICE**, not inherited as a canonical 14-year csvplan rule |
| Observed BEA investment | Diagnostic only in E | Diagnostic comparison only; neither objective nor lower bound | **ALIGNED EMPIRICAL DIAGNOSTIC** |

## Main finding

No numerical solver change is required for csvplan alignment.

The physical/accounting core that survives the architectural change is already consistent with the reconciled reference: vector final-output accounting, exact stock timing, cohort survival/depreciation and explicit feasibility checks. The remaining differences are genuine Milestone F extensions, not unresolved csvplan defects.

The most important provenance correction concerns the 70% schedule. Because final F is a simultaneous LP, it does not have an iterative initialization state comparable to `csvplan.jl`. Saying that F uses a `0% warm start` is therefore technically misleading. The correct statement is: **F imposes no preliminary replacement schedule; investment is an endogenous nonnegative decision variable.** The historical 70% csvplan warm start is simply not part of F's optimization architecture.

## Objective status

The F lexicographic hierarchy is not attributed to Cockshott's printed New Harmony controller:

1. maximize the minimum annual fulfillment `theta`;
2. holding `theta` at its optimum, maximize the piecewise-linear approximation to mean Harmony;
3. holding the first two objectives, minimize total capital-goods final output.

This is a deliberate research extension. Its performance may be compared with E using minimum fulfillment, exact reported Harmony, investment and physical feasibility, but numerical superiority does not retroactively make the lexicographic hierarchy a Cockshott rule.

## Required provenance labels

Aligned F documentation and machine-readable metadata should distinguish at least:

- `csvplan_reconciled_physical_core`: vector accounting, exact stock recurrence, exact investment-cohort depreciation;
- `milestone_e_empirical_inheritance`: 71-sector data construction, labour and import envelope, corrected E numerical baseline;
- `milestone_f_objective`: full-horizon max-min / Harmony / capital lexicographic hierarchy;
- `milestone_f_harmony_approximation`: 81-point tangent representation used only inside stage 2;
- `milestone_f_capital_representation`: effective user-sector capital bundle;
- `milestone_f_asset_source_restriction`: selected reproducible-asset-producing source sectors;
- `milestone_f_historical_C`: ex-post dynamic capital/output diagnostic;
- `milestone_f_boundary`: three stationary shadow years and zero investment in the final computational year;
- `milestone_f_preliminary_schedule`: none; investment is endogenous, not initialized by a 0% or 70% warm-start policy.

## Gate decision

**Alignment is necessary at the provenance/documentation level but not at the numerical-solver level.**

Any future change to the lexicographic objective, capital bundle, asset-source restriction, Harmony approximation or shadow horizon must therefore be tested as a Milestone F design experiment. It must not be described as a generic correction required by the Cockshott source corpus.