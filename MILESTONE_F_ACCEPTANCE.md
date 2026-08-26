# Milestone F Corrected acceptance

Milestone F is accepted if all of the following hold:

1. Milestone E Corrected is the current numerical baseline and reproduces its accepted Harmony and investment-ratio locks.
2. The embedded E solver remains identical to the numerical solver used by the aligned Milestone E branch; E-specific search and boundary rules are not misattributed to Cockshott's source-supported core.
3. The old E+1 path is labelled as a legacy diagnostic and cannot be mistaken for the corrected baseline.
4. E+2 and E+3 retain endogenous investment and pass the corrected annual constraint audit.
5. Final F uses eight computational years and three shadow years while reporting 2019–2023 separately.
6. Final Historical F minimum fulfillment is at least 0.95; final Frozen F is at least 0.89.
7. Final F 2023 stock is at least 0.90 of observed BEA stock in both modes.
8. Final F investment remains endogenous and below observed 2019–2023 BEA investment in both modes.
9. Final F cumulative gross output / BEA improves materially relative to Milestone E Corrected in both modes.
10. The final-year shadow investment is zero and all published/shadow fulfillment values respect the reported physical capital, labour and import bounds within numerical tolerance.
11. Every LP year passes flow-balance, stock-recurrence, capital, labour, import, nonnegative-net-output and nonnegative-investment checks.
12. The E Corrected terminal equation is not combined with F's three shadow years.
13. No preliminary 70% replacement schedule is imposed. Final F is not described as using a competing `0% warm start`; its investment variables are endogenous LP decisions.
14. The full-horizon lexicographic hierarchy, Harmony approximation, effective capital bundle, asset-source restriction, historical dynamic `C_t` and three-shadow-year boundary are explicitly labelled as Milestone F extensions or diagnostics rather than recovered Cockshott rules.
15. The accepted corrected and legacy predecessor archives are both preserved.
16. The machine-readable csvplan alignment contract passes and the full Milestone F test suite remains green without changing the pre-alignment numerical solver.

The acceptance criterion does **not** require exact replication of BEA output or investment. Such a requirement would convert the backtest into a calibration exercise and invalidate the experiment.

The csvplan-alignment criterion also does **not** select F design choices merely because they improve Harmony or fulfillment. Source-supported physical identities are inherited first; F-specific objective and empirical choices retain their explicit experimental status.
