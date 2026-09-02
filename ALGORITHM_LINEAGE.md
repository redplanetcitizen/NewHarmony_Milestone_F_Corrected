# Algorithm Lineage: From the 1993 Harmony Concept to the Tensor Implementation

This document reconstructs the historical lineage of the New Harmony planning
algorithm from primary sources supplied for analysis (Cockshott's book chapter,
design notes, and raw prototype code), independent of this repository's own
Python engine family.

**Scope note.** This covers only the pre-Python material: the 1993 book
chapter, the 2018 `lp_solve`-based Java tool, and the Julia prototypes/design
notes that lead up to `csvplan.jl`. The Python descendants in this repository
and its sibling repositories (`c.py`, `d.py`, `e_corrected.py`,
`csvplan-corrected`, `E+1 Final`, `Motore Normale`, the LP engine `f`) are
deliberately excluded here and left for a later pass.

**Evidentiary standard.** Two different kinds of claim appear below and are
kept visually distinct:
- **Dated** — an explicit, verifiable date (file metadata, copyright header,
  publication date).
- **Undated, ordered by internal evidence** — no file carries a date; the
  ordering is derived from what each source's content presupposes or
  implements relative to the others (documented inline with line references).

Two independent lineages emerge. They share a common problem (multi-year
production planning with capital stock and depreciation) but differ in
objective and solution method, and they never merge in the material examined:

```
LINEAGE A — direct LP, "target fulfillment" objective, exact solver
  2018  nyearplan.java + csvfilereader.java + pcsv.java  (lp_solve)
          │
          ├─ "Documentation for the N-year plan solver" (PDF, undated,
          │   describes the same tool on a 4-product toy economy)
          │
          └─ eumodel.lp  (undated, generated output of the same tool on a
              5-sector / 9-year instance)

LINEAGE B — "Harmony" heuristic, iterative reallocation, no exact solver
  1993  Towards a New Socialism, ch. 6  (Cockshott & Cottrell)
          │  cross-INDUSTRY relaxation, static, piecewise harmony
          ▼
  undated  harmony1.jl   (scalar, comparative statics only, no search loop)
          ▼
  undated  harmony2.jl   (scalar, full 9-step cross-YEAR algorithm)
          ▼
  Dec 2020 "Design for Julia implementation of the New Harmony algorithm" (PDF)
          │  formalizes the tensor/multi-sector generalization of harmony2.jl
          ▼
  undated  csvplan.jl    (tensor, multi-sector Julia implementation)
          ▼
  [Python engine family — out of scope here]
```

---

## Lineage A — the LP / `lp_solve` tool

### 1. `nyearplan.java`, `csvfilereader.java`, `pcsv.java` — dated 2018

**Dated** by an explicit GPL copyright header: *"Copyright (C) 2018 William
Paul Cockshott"* (`nyearplan.java` line 5, `csvfilereader.java` line 13).
This is the earliest firmly-dated artifact examined.

- `pcsv.java` / `csvfilereader.java`: a hand-written recursive-descent CSV
  parser (claimed conformant to a UK government CSV specification cited via
  an `ofgem.gov.uk` link in the Javadoc), representing a parsed file as a
  linked list of cells (`pcsv`/`celltype`/`linestart`/`numeric`/`alpha`).
  Pure I/O infrastructure — no planning logic.
- `nyearplan.java`: reads four CSV matrices (flow, capital, depreciation,
  labour-and-targets — usage string at line 39) and emits an `lp_solve`-format
  LP file. The objective (`maximiser`, lines 122–126) is the **sum of
  per-year target-fulfillment variables** — not a harmony function. Capital
  stock evolves through an explicit linear recursion
  (`accumulationconstraint`, lines 197–201):
  `capital[t] <= capital[t-1] + accumulation[t-1] - depreciation[t-1]`.
  Output is bounded by capital, by intermediate-input flow, and by labour
  through three families of `<=` constraints (`outputequationfor`,
  `flowconstraintfor`, `labourconstraintfor`) — a linearized Leontief
  fixed-coefficient production function (a `min()` expressed as multiple
  inequalities, the standard LP idiom for that constraint shape).

### 2. "Documentation for the N-year plan solver" (PDF) — undated

Describes the same `nyearplan.java`/`lp_solve` tool on a toy 4-product
economy. The stated objective value (6.24052) was independently verified by
hand-summing the five reported per-year target-fulfillment figures
(`0.89881+1.01585+1.4845+1.34227+1.49909=6.24052`), confirming the
objective formula as documented matches `maximiser()` in `nyearplan.java`.
No harmony function appears anywhere in this tool or its documentation.

### 3. `eumodel.lp` — undated, generated output of the 2018 tool

Verified **line-by-line** against `nyearplan.java`'s generator methods (not
merely by resemblance): `maximiser`, `targeqn`, `labourtotal`,
`outputequationfor`, `flowconstraintfor`, `namedep`, and
`accumulationconstraint` each reproduce the corresponding lines of
`eumodel.lp` exactly, coefficient for coefficient. The instance is a
5-sector (AGRICULTURE, INDUSTRY, CONSTRUCTION, SERVICES, FOREIGNTRADE),
9-year economy with a labour force on the order of 5.9–6.0 million — a
realistic macro-scale instance, not the toy example from item 2.

**Flagged discrepancy.** `eumodel.lp` contains 9 bound lines of the form
`targetFulfillmentForYear{n}>0.4;` (one per year) that have **no
corresponding code** in the uploaded `nyearplan.java` — `targeqn()` emits
only `<=` constraints, never a lower bound on the target variable itself.
Either `eumodel.lp` was produced by a different/later version of the
generator than the one supplied, or the bounds were added by hand after
generation (e.g., to exclude the degenerate zero-consumption solution in
early years). This is reported as an open discrepancy, not resolved by the
material available.

---

## Lineage B — the "Harmony" heuristic

### 1. *Towards a New Socialism*, Chapter 6 — 1993, Cockshott & Cottrell

**Dated** by publication (book, 1993; chapter supplied and read in full,
16 pages). Introduces the harmony concept in its original piecewise form:
`u = (output - goal) / goal`; `harmony = -u²` if `u < 0`, else `harmony =
√u`. Describes a **cross-industry** (not cross-year) relaxation algorithm
in 9 stages, claims linear-time complexity, and reports a benchmark
(4000 industries, ~300s on a Sun workstation). No capital-stock dynamics,
depreciation, or multi-year horizon — this is a single-period model.
Includes discussion of Stafford Beer / Project Cybersyn (Chile) as
motivating context.

### 2. `harmony1.jl` — undated

The earliest artifact in this branch of the lineage by internal evidence:
it contains **no iterative search loop at all**. It defines the modern
smooth harmony function `h(x) = x/(1.1+x)` (already different from the
book's piecewise form), a scalar Leontief production function
`computeOutput = min(capital·k, labour·a)`, and a fixed-point iteration
(`computeMinGrossOutputForGoal`, 15 iterations) for the steady-state
capital stock needed to cover depreciation (`depreciationhorizon = 10`).
It then explores unemployment/full-employment implications by rescaling
targets. No worst-year selection, no investment reallocation — this reads
as exploratory groundwork establishing the basic relationships before any
allocation algorithm exists.

### 3. `harmony2.jl` — undated, same era as item 2

Same single-good, 5-year scalar model, but now implements the **complete
9-step iterative algorithm** later formalized in the Design PDF (item 4):
last-year full-employment target (lines 90–97), initial capital stock
depreciated forward with **linear** depreciation (lines 103–113,
`depreciationhorizon = 14`), mean/stdev harmony with a coefficient-of-
variation termination test (`mincoeff = 0.01`), worst-year selection,
upscale estimation via `harmonyInverse(meanh)`, and a source-year search to
fund the reallocation.

Two findings from direct code reading, verified against `csvplan.jl` (which
was analyzed earlier in this conversation):

- **Worst-year selection is genuinely exercised here.** Line 193:
  `lowyear=Select_the_year_with_the_lowest_harmony()` is an active call. In
  `csvplan.jl`, the equivalent call is commented out and replaced by a fixed
  loop order (`lowyear = i`). The destination-selection defect identified
  earlier in `csvplan.jl` is therefore a **regression introduced when moving
  to the tensor/multi-sector version**, not a flaw present in the original
  design.
- **Candidate valuation is analytic, not simulated.** `Attempt_to_scale_up`
  (lines 228–260) evaluates each candidate source-year's gain/loss directly
  from the closed-form harmony expression (`lossfromInvesting`, lines
  236–242) — an O(1) computation per candidate. This is precisely the
  "computationally preferable" shortcut proposed in the Design PDF's
  "Comment on step 8" — which that PDF frames as a proposal, not as
  something already working. It **was** already implemented here, in the
  earliest scalar prototype, and is lost in `csvplan.jl`, whose
  `Attempt_to_scale_up`/`gainfromInvesting` instead re-simulate the entire
  model per candidate (`variant_scenario` → `update_outputs`).

### 4. "Design for Julia implementation of the New Harmony algorithm" (PDF) — dated December 2020

**Dated** via LuaTeX PDF metadata (`pdfinfo`). Sets out the tensor/vector
generalization of the scalar model explicitly described in `harmony2.jl`
("We will first set out a simple scalar model of the accumulation problem
before going on to deal with the full vector form"), reproducing the same
9-step structure and the same smooth harmony function. Its "Comment on
step 8" proposes evaluating candidates via a cheap valuation-vector
computation instead of a full re-simulation — language that, read next to
`harmony2.jl`, describes recovering a technique the scalar prototype
already had, ahead of the tensor implementation that would go on to drop
it.

### 5. `csvplan.jl` — undated, after or concurrent with the Design PDF

The tensor/multi-sector Julia implementation (885 lines, read in full).
Confirmed regressions relative to `harmony2.jl`, both consequential for
solution quality:
1. `lowyear = i  #Select_the_year_with_the_lowest_harmony(...)` — the
   worst-year selection call is present but commented out; the year is
   instead picked by fixed loop order.
2. `Attempt_to_scale_up`/`gainfromInvesting` evaluate each candidate by a
   full model re-simulation (`variant_scenario` → `update_outputs`), an
   expensive path the Design PDF's "Comment on step 8" explicitly wanted to
   avoid and which `harmony2.jl` had already avoided via its analytic
   `lossfromInvesting`.

`grossOutputForDemandf` also recomputes `inv(I-A)` from scratch on every
call (O(N³)), ignoring the precomputed `problem.InvIA` available on the
problem object — a separate, purely computational inefficiency (not an
economic-outcome defect) noted for completeness.

---

## Summary of firmly-established facts vs. open questions

**Established with a verifiable source:**
- 1993 — book publication date (external, well known).
- 2018 — `nyearplan.java`/`csvfilereader.java`/`pcsv.java` copyright header.
- Dec 2020 — Design for Julia PDF, via embedded LuaTeX metadata.
- `eumodel.lp` is the literal generator output of `nyearplan.java`, verified
  clause-by-clause.
- `harmony2.jl`'s worst-year selection is live; `csvplan.jl`'s equivalent is
  disabled — a code-level regression, not a matter of interpretation.
- `harmony2.jl`'s candidate evaluation is analytic; `csvplan.jl`'s is a full
  re-simulation — likewise a direct code comparison, not inference.

**Ordered by internal evidence, not independently dated:**
- `harmony1.jl` precedes `harmony2.jl` (simpler, no search loop at all).
- `harmony2.jl` precedes the Design PDF (the PDF formalizes what the script
  already does).
- `csvplan.jl` follows the Design PDF (implements its tensor generalization)
  but diverges from it on the two points above.

**Open / unresolved:**
- The exact dates of `harmony1.jl`, `harmony2.jl`, and `csvplan.jl`.
- The `targetFulfillmentForYear{n}>0.4` bounds in `eumodel.lp`, unexplained
  by the `nyearplan.java` source supplied.
- Whether Lineage A (`nyearplan.java`) and Lineage B (`harmony1.jl` onward)
  had any direct interaction beyond sharing an author and a problem domain
  — no cross-reference between them was found in any source examined.
