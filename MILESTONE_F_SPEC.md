# Milestone F Corrected specification

## Purpose

Extend the accepted Milestone E Corrected benchmark with F's full-horizon lexicographic planner without calibrating New Harmony to observed BEA investment.

## Invariants retained from E

- 71 BEA Summary sectors.
- 2019-price real output/capital/investment/depreciation quantities.
- BEA FTE labour constraint.
- Domestic social final-demand target construction; observed fixed investment remains excluded from the plan ray.
- Intermediate imports are an exogenous componentwise envelope, not a foreign-sector closure.
- Investment produced in year `t` becomes productive at start `t+1`.
- Stock dynamics remain `S[t+1] = (1-D[t]) * S[t] + I[t]`.
- Harmony function remains `H(f) = f / (1.1 + f)`.
- Non-terminal investment starts without a general maintenance floor; no 70% replacement rule is used.
- Net output satisfies `(I-A_t)x_t = f_t g_t + p_t`, where `p_t` is capital-goods final output.
- Investment is nonnegative and becomes productive only at the start of the following year.

## Corrected baseline and annual audit

- `new_harmony_empirical_e_corrected.py` is the current E baseline.
- The original E+1 implementation is retained only as a labelled legacy diagnostic.
- Each LP solution is rejected if any year fails flow balance, exact stock recurrence, capital, labour, imports, nonnegative net output or nonnegative investment.
- Observed investment is used only for reported comparison ratios.

## F objective hierarchy

1. Maximize `theta = min_t f_t`.
2. Holding `theta` at its optimum, maximize mean Harmony using an 81-point piecewise-linear concave approximation on `0 <= f <= 1`.
3. Holding the first two objectives, minimize total capital-goods production.

Thus Harmony determines efficiency among plans that are already as close as possible to meeting the worst annual target.  It no longer decides whether a necessary target-improving investment should be rejected because of a fall in average Harmony.

## Capital representation

E+2 preserves the Milestone E source×user cell minimum exactly.

E+3/F uses an effective capital bundle by user sector.  This is a deliberate response to the empirical construction of `C`: its source composition comes from the 1997 BEA Capital Flow Table and contains acquisition/distribution service rows.  At 71-sector aggregation these rows are not treated as separate fixed-proportion productive machines.  Their capitalized value is folded into the user-sector bundle.  New investment is restricted to source sectors that correspond to structures, equipment or IPP-producing activities.

Frozen: sector capital/output coefficients remain at 2019 values.

Historical: `C_t,total(j) = K_observed,start(t,j) / X_observed(t,j)` for 2019–2023.  This is an ex-post diagnostic.  Shadow years repeat the latest stationary observed ratio.

## Horizon

Published horizon: 2019–2023.

Computational horizon in final F: 2019–2026.  Years 2024–2026 are stationary shadows repeating the latest available target, technology, labour and import assumptions.  Investment in the final computational year is fixed to zero because it has no modeled future use; in an operational receding-horizon planner the horizon is rolled forward before that year becomes published.

The terminal equation used by Milestone E Corrected is not applied to final F. The three shadow years are F's alternative boundary treatment. Combining the two would impose two terminal-capital mechanisms on the same horizon.
