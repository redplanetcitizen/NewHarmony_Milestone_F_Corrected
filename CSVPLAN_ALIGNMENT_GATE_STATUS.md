# Milestone F csvplan alignment gate

## Result

**PASS for provenance/core alignment.**

Validated branch head before this status note: `b0b22a5a46de0f181cbe1690dcb8bc70e0cdab71`.

GitHub Actions run: `32936984423`, job `98079990210`, conclusion `success`.

The full test suite ran **24 tests, all passing**: the original 14 Milestone F acceptance tests plus 10 dedicated csvplan-alignment tests. Direct contract validation also passed and emitted profile `milestone_f_csvplan_reconciled_alignment`.

## What this gate establishes

1. The pre-alignment F numerical baseline remains pinned to `d71a68c6f02cde756ed814b8e209b23177ab56e0`.
2. `code/new_harmony_empirical_f.py` remains byte-for-byte at Git blob `8595c488031c334e5558e1b3be5960cee3ca3fa5`.
3. The embedded E numerical solver remains Git blob `193fce86af7a7497035bb3407e3ec972a8598bc2`, identical to the aligned E numerical solver.
4. The reconciled csvplan checkpoint is pinned to `ded576c5b8c80d2bbc9fbf3a8a7a391f0a64a433`.
5. Vector accounting, stock timing, cohort depreciation and physical admissibility are explicitly retained as reconciled physical core.
6. Iterative-controller rules such as destination scan, source-year search, C26 epsilon update, epsilon control and CV stopping are marked not applicable to final F's simultaneous LP.
7. Final F is explicitly recorded as having **no warm-start semantics**. It imposes no preliminary 70% schedule; investment is an endogenous nonnegative LP variable rather than a `0% warm start`.
8. The full-horizon lexicographic objective is a Milestone F extension.
9. The 81-point Harmony tangent approximation is a Milestone F numerical extension.
10. Effective capital bundles, asset-source restriction and Historical dynamic `C_t` are Milestone F empirical extensions/diagnostics.
11. Three stationary shadow years are a Milestone F boundary extension, not a canonical csvplan terminal rule.

## Numerical decision

No solver revision is required for csvplan alignment. The audit found no surviving physical/core conflict in the final F formulation that would justify altering `new_harmony_empirical_f.py`.

Future changes to the lexicographic hierarchy, capital bundle, Harmony approximation, asset-source restriction or shadow horizon must be treated as explicit Milestone F experiments and evaluated separately. They must not be introduced under the label of a generic Cockshott/csvplan correction.
