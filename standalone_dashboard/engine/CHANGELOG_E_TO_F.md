# Changelog E -> F

Historical design sequence retained for provenance. In Milestone F Corrected the current baseline is E Corrected; see `CHANGELOG_F_CORRECTED.md` and `CORRECTIONS_AUDIT.md`.

- F01: preserve Milestone E as immutable benchmark/reference.
- F02: introduce lexicographic max-min fulfillment before Harmony.
- F03: replace local investment acceptance as the sole planning mechanism with a full multiperiod forward-looking feasibility/accumulation layer.
- F04: cap social fulfillment at 1.0; target surplus is not rewarded in the primary objective.
- F05: retain `H(f)=f/(1.1+f)` as the secondary objective via piecewise-linear approximation.
- F06: minimize investment only after max-min fulfillment and Harmony are fixed.
- F07: add sector-effective capital-bundle representation for the BEA-71 empirical application; fold capitalized margin/service source rows into underlying productive assets and restrict new capital production to asset-bearing source sectors.
- F08: add Historical diagnostic `C_t` from observed start-of-year capital/output ratios; Frozen remains fixed at 2019.
- F09: extend final computational horizon by three stationary shadow years.
- F10: preserve M08 import envelope and M09 inventory interpretation from E; inventories remain outside the F LP because they were a verified zero-transfer module in the accepted real backtest.
