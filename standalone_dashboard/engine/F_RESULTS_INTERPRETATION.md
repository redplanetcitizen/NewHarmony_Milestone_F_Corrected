# Milestone F Corrected — interpretation of the experiment

## What changed relative to E

The corrected comparison replaces the obsolete E benchmark used by the original F package. E Corrected invests 26.88% of observed investment in Frozen mode and 27.47% in Historical mode, rather than the 6–7% reported by legacy E. F's structural conclusions nevertheless remain: full-horizon control and the effective capital bundle materially increase fulfillment and terminal stock.

The original local Harmony acceptance rule was too restrictive for a problem in which current investment must be paid before future capacity appears. E+2 replaces that local horizon with a simultaneous five-year capacity calculation. The old E+1 run remains only as a labelled legacy diagnostic and is not part of the corrected baseline.

Second, the empirical source×user capital matrix was being interpreted more literally than its data support.  Its source composition is inherited from the 1997 Capital Flow Table and includes capitalized distribution/service components.  Treating every one of those cells as a perfect, non-substitutable productive complement creates false precision at the 71-sector level.  E+3 folds those components into an effective sector capital bundle and limits new investment production to asset-bearing sectors.  This is the largest structural gain: minimum fulfillment rises to 0.906 Frozen and 0.973 Historical.

## The cost of terminal robustness

E+4 adds three shadow years.  This slightly lowers published-horizon fulfillment because the years 2019–2023 must finance capacity that remains useful through 2026, but it strongly raises the capital stock left at the end of 2023.

Frozen 2023 stock rises from 78.74% of BEA in E Corrected to 91.26% in F Corrected. Historical rises from 78.86% to 91.47%. The corresponding 2019–2023 investment rises from 26.88% to 71.83% in Frozen and from 27.47% to 70.88% in Historical.

This is not calibration to BEA. Historical investment never appears in the objective or as a floor. The higher investment is generated endogenously by the combination of max-min fulfillment and the additional future periods over which capital has value. Its numerical proximity to 70% is not a replacement-floor rule.

## Why F does not reach exactly 1.0

Final F reaches minimum fulfillment 0.899 in Frozen and 0.967 in Historical.  The remaining Frozen shortfall is particularly informative: the imported-intermediate envelope becomes binding together with capacity in several years.  With 2019 technology/trade structure frozen, the stated targets plus endogenous accumulation and three future shadow periods are not fully feasible under the retained resource envelopes.

Historical is much closer to full fulfillment because observed changes in technology and capital intensity are admitted ex post.  It should therefore be read as a diagnostic upper-performance benchmark, not as a forecast that could have been produced with 2019 information.

## Output comparison

The five-year gross-output ratio relative to BEA improves substantially:

- Frozen: 0.7019 in E Corrected to 0.8658 in F Corrected.
- Historical: 0.7075 in E Corrected to 0.9253 in F Corrected.

The result is consistent with the purpose of F: it does not force the model to reproduce BEA gross output, but much of the earlier output gap disappears when the planner prevents capital from eroding and removes the empirically over-rigid cell-level interpretation of capital.

## Status of the Harmony objective

Harmony is retained exactly as `H(f)=f/(1.1+f)`, but it is now secondary.  The solver first maximizes the worst annual fulfillment.  It then maximizes an 81-point piecewise-linear concave approximation to total Harmony, whose maximum approximation error on `0 <= f <= 1` is about `3.2e-5`.  Only after those two objectives are fixed does it minimize investment.

This is the principal theoretical change from E: Harmony decides how to rank plans that are already as successful as possible in meeting the targets; it no longer decides whether a target-improving accumulation should be abandoned simply because its current cost reduces average Harmony.

## Architectural status

Milestone F should therefore not be described as an unchanged implementation of `csvplan.jl`.  It is a **hybrid lexicographic extension of New Harmony**.  The New Harmony elements retained are the plan ray, Leontief propagation, capital accumulation/depreciation, intertemporal sacrifice and the Harmony function.  The new elements are the max-min primary objective, full-horizon capacity control, effective empirical capital aggregation and rolling-horizon terminal treatment.

The corrected package makes the boundary distinction explicit. E Corrected uses a terminal equation; F Corrected uses three stationary shadow years. Only the latter is active in final F, avoiding double counting. All published and shadow years pass the exported corrected constraint audit.
