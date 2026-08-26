# Provenance

Milestone F Corrected is a research extension built on the empirical Milestone E Corrected baseline. It is not a direct implementation of Cockshott's `csvplan.jl` controller.

## Pinned checkpoints

- Reconciled csvplan implementation: `redplanetcitizen/csvplan-corrected` commit `ded576c5b8c80d2bbc9fbf3a8a7a391f0a64a433`.
- Milestone E accepted numerical baseline: `redplanetcitizen/NewHarmony_E_Corrected` commit `3faf1657bf0df93906477ed3ba85766406f323ba`.
- Milestone E csvplan-alignment gate: branch `align-csvplan-reconciled`, commit `eecbc29ec6b82a677545eca4f9540d1623328d98`.
- Milestone F pre-alignment numerical baseline: `d71a68c6f02cde756ed814b8e209b23177ab56e0`.
- Embedded `code/new_harmony_empirical_e_corrected.py` Git blob: `193fce86af7a7497035bb3407e3ec972a8598bc2`, identical to the solver blob in the aligned E branch.

## Inherited source-supported physical core

F retains the parts of the reconciled core that remain meaningful under simultaneous optimization:

- vector accounting of social output and capital-goods final output;
- exact annual stock recurrence;
- investment produced in `t` becoming productive at start `t+1`;
- exact cell-specific depreciation of earlier investment cohorts;
- explicit physical feasibility checks.

Robust annual Harmony is represented equivalently within F's common plan-ray restriction: every positive-target product has the same annual fulfillment factor `f_t`, so the minimum product Harmony is `H(f_t)`.

## Milestone E empirical inheritance

F inherits the 71-sector BEA data construction, labour treatment, import envelope and corrected E numerical baseline. These are empirical-model choices, not parts of the five-sector historical csvplan witness.

## Milestone F extensions

The following are specific to F and must not be attributed to Cockshott's printed New Harmony controller:

- simultaneous full-horizon linear programming;
- lexicographic objective: worst fulfillment, then approximate mean Harmony, then capital-goods minimization;
- 81-point tangent approximation to Harmony inside the optimization;
- effective user-sector capital bundle;
- asset-source restriction for new investment;
- ex-post dynamic capital/output coefficients in Historical mode;
- three stationary shadow years as terminal treatment.

## Preliminary investment

Final F has no iterative warm-start policy. It neither imports the historical `csvplan.jl` 70% preliminary replacement schedule nor replaces it with a theoretically privileged 0% schedule. Investment is a nonnegative endogenous LP decision variable from the outset.

## Boundary treatment

F does not combine Milestone E's terminal equation with the three shadow years. The shadow horizon is an F boundary extension. Its length and stationary repeat-last assumptions are not presented as canonical consequences of the historical csvplan 14-year demonstration policy.

## Numerical status

The csvplan alignment audit requires no numerical change to `code/new_harmony_empirical_f.py`. Its role is to make the inheritance boundary explicit and machine-testable. See `CSVPLAN_RECONCILED_ALIGNMENT.md` and `code/csvplan_reconciled_alignment.py`.
