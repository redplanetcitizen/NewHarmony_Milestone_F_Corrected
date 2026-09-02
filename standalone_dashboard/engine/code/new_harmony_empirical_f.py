from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import copy
import csv
import json
import math
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix, csr_matrix, vstack

import new_harmony_empirical_c as c
import new_harmony_empirical_d as d
import new_harmony_empirical_e_corrected as ec

HARMONY_GRID = np.linspace(0.0, 1.0, 81)
TOL = 1e-9
AUDIT_ATOL = 1e-6
AUDIT_RTOL = 1e-8

# Capital-flow rows that represent reproducible fixed assets at the 71-sector level.
# Trade/transport/real-estate margins contained in the 1997 CFT composition are folded
# into the underlying asset bundle rather than treated as independent productive stocks.
ASSET_SOURCE_CODES = {
    '212','213','23','313TT','321','325','326','332','333','334','335',
    '3361MV','3364OT','337','339','511','5415','5412OP'
}


@dataclass(frozen=True)
class YearConstraintAudit:
    year: int
    flow_balance_error: float
    stock_recurrence_error: float
    max_capital_excess: float
    labour_excess: float
    max_import_excess: float
    min_net_output: float
    min_investment: float
    flow_balance_ok: bool
    stock_recurrence_ok: bool
    capital_ok: bool
    labour_ok: bool
    imports_ok: bool
    net_output_ok: bool
    investment_ok: bool
    compliant: bool

@dataclass
class LPResult:
    label: str
    mode: str
    years: list[int]
    published_years: int
    theta: float
    f: np.ndarray
    investments: np.ndarray
    p: np.ndarray
    stock_start: np.ndarray
    stock_end: np.ndarray
    gross_realized: np.ndarray
    net_output: np.ndarray
    mean_harmony_published: float
    min_fulfillment_published: float
    mean_harmony_all: float
    min_fulfillment_all: float
    investment_published: float
    investment_all: float
    stock_terminal_published: float
    stock_terminal_all: float
    capital_constraint: np.ndarray
    labour_constraint: np.ndarray
    import_constraint: np.ndarray
    constraint_audit: list[YearConstraintAudit]
    stage1_status: str
    stage2_status: str
    stage3_status: str


def harmony_mean(f: np.ndarray) -> float:
    return float(np.mean(c.harmony(np.asarray(f, float))))


def _lex_score(s: d.DScenario) -> tuple[float, float]:
    return float(np.min(s.feasible_ratio)), float(s.mean_harmony)


def solve_eplus1(data: c.ModelData, trade: d.TradeInventoryData,
                 maxiter: int = 1200) -> tuple[d.DScenario, d.DScenario, list[dict], str]:
    """E+1: change only the search objective.

    Proposal generation remains the New-Harmony/D mechanism (worst year, epsilon-sized
    Harmony step, targeted cell-level capital gap).  Candidate acceptance becomes
    lexicographic: maximize the minimum annual fulfillment first, then mean Harmony.
    """
    T, N = data.goals.shape
    inv = np.zeros((T, N, N), float)
    q = np.zeros((T, T, N), float)
    current = d.evaluate_d(data, trade, inv, q, imports_enabled=True, inventories_enabled=False)
    initial = current
    logs: list[dict] = []
    for it in range(1, maxiter + 1):
        dest = int(np.argmin(current.feasible_ratio))
        if dest == 0:
            return initial, current, logs, 'lowest_year_has_no_predecessor'
        desired, current_f, step, _, gap = d.capital_gap_for_harmony_step(
            data, current, dest, d.DEFAULT_EPSILON
        )
        if step <= d.GAIN_TOL or gap.sum() <= d.GAIN_TOL or not np.isfinite(gap).all():
            return initial, current, logs, 'no_capital_gap'
        old_score = _lex_score(current)
        best = None
        for src in range(dest):
            cand = d.inverse_depreciate_gap(gap, data, src, dest)
            if not np.isfinite(cand).all():
                continue
            inv2 = current.investments.copy()
            inv2[src] += cand
            v = d.evaluate_d(data, trade, inv2, q, imports_enabled=True, inventories_enabled=False)
            if np.any(v.imported_intermediate_required - v.imported_intermediate_cap > 1e-7):
                continue
            score = _lex_score(v)
            improves = score[0] > old_score[0] + TOL or (
                abs(score[0] - old_score[0]) <= TOL and score[1] > old_score[1] + TOL
            )
            if not improves:
                continue
            key = (score[0], score[1], -float(cand.sum()))
            if best is None or key > best[0]:
                best = (key, src, cand, v)
        if best is None:
            return initial, current, logs, 'no_lexicographic_positive_transfer'
        key, src, cand, new = best
        logs.append({
            'iteration': it,
            'source_year': data.years[src],
            'destination_year': data.years[dest],
            'min_fulfillment_before': old_score[0],
            'min_fulfillment_after': key[0],
            'mean_harmony_before': old_score[1],
            'mean_harmony_after': key[1],
            'investment_real_musd': float(cand.sum()),
            'desired_destination_fulfillment': desired,
            'epsilon_step': step,
        })
        current = new
    return initial, current, logs, 'maxiter'


def extend_with_shadows(data: c.ModelData, trade: d.TradeInventoryData,
                        n_shadow: int) -> tuple[c.ModelData, d.TradeInventoryData]:
    if n_shadow <= 0:
        return copy.deepcopy(data), copy.deepcopy(trade)
    N = len(data.sectors)
    last = data.years[-1]
    years = data.years + [last + k for k in range(1, n_shadow + 1)]
    A = np.concatenate([data.A_by_year, np.repeat(data.A_by_year[-1][None, :, :], n_shadow, axis=0)])
    L = np.concatenate([data.L_by_year, np.repeat(data.L_by_year[-1][None, :, :], n_shadow, axis=0)])
    dep = np.concatenate([data.dep_by_year, np.repeat(data.dep_by_year[-1][None, :, :], n_shadow, axis=0)])
    goals = np.concatenate([data.goals, np.repeat(data.goals[-1][None, :], n_shadow, axis=0)])
    lcoef = np.concatenate([data.labour_coeff_by_year,
                            np.repeat(data.labour_coeff_by_year[-1][None, :], n_shadow, axis=0)])
    lav = np.concatenate([data.labour_available, np.repeat(data.labour_available[-1], n_shadow)])
    og = {k: v.copy() for k, v in data.observed_gross.items()}
    os = {k: v.copy() for k, v in data.observed_stock.items()}
    oi = {k: v.copy() for k, v in data.observed_investment.items()}
    for y in years[len(data.years):]:
        og[y] = data.observed_gross[last].copy()
        os[y] = data.observed_stock[last].copy()
        oi[y] = np.zeros(N)
    md = c.ModelData(years, data.sectors, data.names, A, L, data.C.copy(), dep,
                     data.initial_stock.copy(), goals, lcoef, lav, og, os, oi, data.mode)
    impA = np.concatenate([trade.import_A_by_year,
                           np.repeat(trade.import_A_by_year[-1][None, :, :], n_shadow, axis=0)])
    impcap = np.concatenate([trade.import_cap_by_year,
                             np.repeat(trade.import_cap_by_year[-1][None, :], n_shadow, axis=0)])
    invchange = np.concatenate([trade.inventory_change_real, np.zeros((n_shadow, N))])
    tr = d.TradeInventoryData(impA, impcap, invchange, np.abs(invchange))
    return md, tr


def capital_total_coefficients(data: c.ModelData, published_years: int,
                               dynamic_historical: bool) -> np.ndarray:
    """Return sector-total capital/output coefficients for each computational year.

    Frozen mode keeps 2019 coefficients. Historical mode is a diagnostic/ex-post mode:
    for observed years t, total C_t,j = observed stock at start-t / observed real gross
    output_t. Shadow years repeat the latest observable stationary ratio K_2023/X_2023.
    """
    T, N = data.goals.shape
    base = data.C.sum(axis=0)
    out = np.repeat(base[None, :], T, axis=0)
    if not dynamic_historical:
        return out
    original_last = 2023
    for t, y in enumerate(data.years):
        if t < published_years:
            prev = 2018 if y == 2019 else y - 1
            if prev in data.observed_stock and y in data.observed_gross:
                x = data.observed_gross[y]
                out[t] = np.divide(data.observed_stock[prev], x,
                                   out=base.copy(), where=x > 1e-12)
        else:
            x = data.observed_gross[original_last]
            out[t] = np.divide(data.observed_stock[original_last], x,
                               out=out[t-1].copy(), where=x > 1e-12)
    return out


def _build_lp(data: c.ModelData, trade: d.TradeInventoryData, *,
              cap_mode: str, dynamic_historical_C: bool,
              published_years: int, restrict_asset_sources: bool):
    T, N = data.goals.shape
    Ctotal = capital_total_coefficients(
        data, published_years, dynamic_historical_C and data.mode == 'historical'
    )
    # Variable layout: theta | f[T] | h[T] | p[T,N] | I[T,N,N]
    i_theta = 0
    i_f = 1
    i_h = i_f + T
    i_p = i_h + T
    i_I = i_p + T * N
    nvar = i_I + T * N * N
    def pidx(t, i): return i_p + t * N + i
    def Iidx(t, i, j): return i_I + t * N * N + i * N + j

    cap_rows = T * N * N if cap_mode == 'cell' else T * N
    harmony_rows = T * len(HARMONY_GRID)
    n_ub = T + cap_rows + T + T * N + harmony_rows
    A = lil_matrix((n_ub, nvar), dtype=float)
    b = np.zeros(n_ub, float)
    row = 0

    # theta <= f_t
    for t in range(T):
        A[row, i_theta] = 1.0
        A[row, i_f + t] = -1.0
        row += 1

    # Survival of initial cell stock to each start-of-year state.
    init_cells = [data.initial_stock.copy()]
    for t in range(1, T):
        init_cells.append(init_cells[-1] * (1.0 - data.dep_by_year[t - 1]))

    for t in range(T):
        gross_social = data.L_by_year[t] @ data.goals[t]
        if cap_mode == 'cell':
            C = data.C
            for i in range(N):
                for j in range(N):
                    cij = C[i, j]
                    if cij <= 1e-12:
                        b[row] = 1e30
                        row += 1
                        continue
                    A[row, i_f + t] = cij * gross_social[j]
                    for k in range(N):
                        val = cij * data.L_by_year[t][j, k]
                        if abs(val) > 1e-14:
                            A[row, pidx(t, k)] = val
                    for s in range(t):
                        survival = 1.0
                        for k in range(s + 1, t):
                            survival *= 1.0 - data.dep_by_year[k][i, j]
                        A[row, Iidx(s, i, j)] = -survival
                    b[row] = init_cells[t][i, j]
                    row += 1
        elif cap_mode == 'sector_bundle':
            for j in range(N):
                cj = Ctotal[t, j]
                if cj <= 1e-12:
                    b[row] = 1e30
                    row += 1
                    continue
                A[row, i_f + t] = cj * gross_social[j]
                for k in range(N):
                    val = cj * data.L_by_year[t][j, k]
                    if abs(val) > 1e-14:
                        A[row, pidx(t, k)] = val
                for s in range(t):
                    for i in range(N):
                        survival = 1.0
                        for k in range(s + 1, t):
                            survival *= 1.0 - data.dep_by_year[k][i, j]
                        A[row, Iidx(s, i, j)] = -survival
                b[row] = float(init_cells[t][:, j].sum())
                row += 1
        else:
            raise ValueError(cap_mode)

    # Labour.
    for t in range(T):
        gs = data.L_by_year[t] @ data.goals[t]
        A[row, i_f + t] = float(data.labour_coeff_by_year[t] @ gs)
        lp = data.labour_coeff_by_year[t] @ data.L_by_year[t]
        for i, val in enumerate(lp):
            if abs(val) > 1e-14:
                A[row, pidx(t, i)] = val
        b[row] = data.labour_available[t]
        row += 1

    # Imported intermediate envelope.
    for t in range(T):
        gs = data.L_by_year[t] @ data.goals[t]
        social_import = trade.import_A_by_year[t] @ gs
        capital_import = trade.import_A_by_year[t] @ data.L_by_year[t]
        for r in range(N):
            A[row, i_f + t] = social_import[r]
            for i, val in enumerate(capital_import[r]):
                if abs(val) > 1e-14:
                    A[row, pidx(t, i)] = val
            b[row] = trade.import_cap_by_year[t, r]
            row += 1

    # Piecewise-linear concave approximation to Harmony using tangent upper envelope.
    for t in range(T):
        for x0 in HARMONY_GRID:
            h0 = float(c.harmony(x0))
            slope = c.HARMONY_OFFSET / (c.HARMONY_OFFSET + x0) ** 2
            intercept = h0 - slope * x0
            # h_t <= slope*f_t + intercept
            A[row, i_h + t] = 1.0
            A[row, i_f + t] = -slope
            b[row] = intercept
            row += 1
    assert row == n_ub

    # p_t,i = sum_j I_t,i,j
    Aeq = lil_matrix((T * N, nvar), dtype=float)
    beq = np.zeros(T * N, float)
    rr = 0
    for t in range(T):
        for i in range(N):
            Aeq[rr, pidx(t, i)] = 1.0
            for j in range(N):
                Aeq[rr, Iidx(t, i, j)] = -1.0
            rr += 1

    hmax = float(c.harmony(1.0))
    bounds = [(0.0, 1.0)]               # theta
    bounds += [(0.0, 1.0)] * T           # fulfillment capped at target
    bounds += [(0.0, hmax)] * T          # PWL Harmony
    bounds += [(0.0, None)] * (T * N)    # capital-goods final output p
    bounds += [(0.0, None)] * (T * N * N)

    if restrict_asset_sources:
        asset_idx = {data.sectors.index(code) for code in ASSET_SOURCE_CODES if code in data.sectors}
        for t in range(T):
            for i in range(N):
                if i not in asset_idx:
                    bounds[pidx(t, i)] = (0.0, 0.0)
                    for j in range(N):
                        bounds[Iidx(t, i, j)] = (0.0, 0.0)

    # Last computational year cannot create capacity inside the modeled horizon.
    for i in range(N):
        bounds[pidx(T - 1, i)] = (0.0, 0.0)
        for j in range(N):
            bounds[Iidx(T - 1, i, j)] = (0.0, 0.0)

    idx = {'theta': i_theta, 'f': i_f, 'h': i_h, 'p': i_p, 'I': i_I,
           'T': T, 'N': N, 'nvar': nvar}
    return csr_matrix(A), b, csr_matrix(Aeq), beq, bounds, idx, Ctotal


def _scaled_ok(excess: float, scale: float) -> bool:
    return excess <= AUDIT_ATOL + AUDIT_RTOL * max(1.0, scale)


def _build_constraint_audit(
    data: c.ModelData,
    trade: d.TradeInventoryData,
    *,
    f: np.ndarray,
    p: np.ndarray,
    investments: np.ndarray,
    stock_start: np.ndarray,
    stock_end: np.ndarray,
    gross: np.ndarray,
    net_output: np.ndarray,
    Ctotal: np.ndarray,
    cap_mode: str,
) -> list[YearConstraintAudit]:
    """Verify the corrected E accounting identities on an F solution.

    F deliberately uses a sector bundle in its final variant and stationary shadow
    years instead of E's cell-level terminal equation.  All other annual flow,
    resource and stock identities are checked here against the solved physical path.
    """
    T, N = data.goals.shape
    reports: list[YearConstraintAudit] = []
    for t in range(T):
        expected_final = f[t] * data.goals[t] + p[t]
        flow_error = float(np.max(np.abs(net_output[t] - expected_final)))
        flow_scale = float(max(np.max(np.abs(net_output[t])), np.max(np.abs(expected_final)), 1.0))

        expected_stock_end = stock_start[t] * (1.0 - data.dep_by_year[t]) + investments[t]
        stock_error = float(np.max(np.abs(stock_end[t] - expected_stock_end)))
        stock_scale = float(max(np.max(np.abs(stock_end[t])), np.max(np.abs(expected_stock_end)), 1.0))

        if cap_mode == 'cell':
            required_capital = data.C * gross[t][None, :]
            capital_excess = float(np.max(required_capital - stock_start[t]))
            capital_scale = float(max(np.max(np.abs(required_capital)), np.max(np.abs(stock_start[t])), 1.0))
        else:
            required_capital = Ctotal[t] * gross[t]
            available_capital = stock_start[t].sum(axis=0)
            capital_excess = float(np.max(required_capital - available_capital))
            capital_scale = float(max(np.max(np.abs(required_capital)), np.max(np.abs(available_capital)), 1.0))

        labour_used = float(data.labour_coeff_by_year[t] @ gross[t])
        labour_excess = labour_used - float(data.labour_available[t])
        import_required = trade.import_A_by_year[t] @ gross[t]
        import_excess = float(np.max(import_required - trade.import_cap_by_year[t]))
        min_net = float(np.min(net_output[t]))
        min_investment = float(np.min(investments[t]))

        flow_ok = _scaled_ok(flow_error, flow_scale)
        recurrence_ok = _scaled_ok(stock_error, stock_scale)
        capital_ok = _scaled_ok(capital_excess, capital_scale)
        labour_ok = _scaled_ok(labour_excess, float(data.labour_available[t]))
        imports_ok = _scaled_ok(import_excess, float(np.max(np.abs(trade.import_cap_by_year[t]))))
        net_output_ok = min_net >= -(AUDIT_ATOL + AUDIT_RTOL * flow_scale)
        investment_ok = min_investment >= -AUDIT_ATOL
        compliant = all((flow_ok, recurrence_ok, capital_ok, labour_ok,
                         imports_ok, net_output_ok, investment_ok))
        reports.append(YearConstraintAudit(
            year=data.years[t],
            flow_balance_error=flow_error,
            stock_recurrence_error=stock_error,
            max_capital_excess=capital_excess,
            labour_excess=labour_excess,
            max_import_excess=import_excess,
            min_net_output=min_net,
            min_investment=min_investment,
            flow_balance_ok=flow_ok,
            stock_recurrence_ok=recurrence_ok,
            capital_ok=capital_ok,
            labour_ok=labour_ok,
            imports_ok=imports_ok,
            net_output_ok=net_output_ok,
            investment_ok=investment_ok,
            compliant=compliant,
        ))
    return reports


def solve_lexicographic_lp(data: c.ModelData, trade: d.TradeInventoryData, *,
                           label: str, cap_mode: str,
                           dynamic_historical_C: bool,
                           published_years: int = 5,
                           restrict_asset_sources: bool = False) -> LPResult:
    A, b, Aeq, beq, bounds, ix, Ctotal = _build_lp(
        data, trade, cap_mode=cap_mode, dynamic_historical_C=dynamic_historical_C,
        published_years=published_years, restrict_asset_sources=restrict_asset_sources
    )
    T, N, nvar = ix['T'], ix['N'], ix['nvar']

    # Stage 1: maximize worst-year fulfillment theta.
    obj1 = np.zeros(nvar)
    obj1[ix['theta']] = -1.0
    r1 = linprog(obj1, A_ub=A, b_ub=b, A_eq=Aeq, b_eq=beq,
                 bounds=bounds, method='highs')
    if not r1.success:
        raise RuntimeError(f'{label} stage1 failed: {r1.message}')
    theta_star = float(r1.x[ix['theta']])

    # Stage 2: preserve theta, maximize mean Harmony (PWL approximation).
    bounds2 = list(bounds)
    bounds2[ix['theta']] = (max(0.0, theta_star - 1e-8), 1.0)
    obj2 = np.zeros(nvar)
    obj2[ix['h']:ix['h'] + T] = -1.0
    r2 = linprog(obj2, A_ub=A, b_ub=b, A_eq=Aeq, b_eq=beq,
                 bounds=bounds2, method='highs')
    if not r2.success:
        raise RuntimeError(f'{label} stage2 failed: {r2.message}')
    h_star = float(r2.x[ix['h']:ix['h'] + T].sum())

    # Stage 3: preserve theta and Harmony, minimize total capital-goods production.
    extra = lil_matrix((1, nvar), dtype=float)
    extra[0, ix['h']:ix['h'] + T] = -1.0
    A3 = vstack([A, csr_matrix(extra)])
    b3 = np.concatenate([b, [-(h_star - 5e-7)]])
    obj3 = np.zeros(nvar)
    obj3[ix['p']:ix['p'] + T * N] = 1.0
    r3 = linprog(obj3, A_ub=A3, b_ub=b3, A_eq=Aeq, b_eq=beq,
                 bounds=bounds2, method='highs', options={'time_limit': 90.0})
    if not r3.success:
        # Stage 2 is always a valid lexicographic solution; retain it if the final
        # parsimony stage hits the time limit.
        chosen = r2
        stage3_status = f'fallback_stage2: {r3.message}'
    else:
        chosen = r3
        stage3_status = r3.message

    z = chosen.x
    f = z[ix['f']:ix['f'] + T].copy()
    p = z[ix['p']:ix['p'] + T * N].reshape(T, N).copy()
    investments = np.array([
        z[ix['I'] + t * N * N:ix['I'] + (t + 1) * N * N].reshape(N, N)
        for t in range(T)
    ])

    # Reconstruct physical paths and constraints for verification/reporting.
    stock_start = np.zeros((T, N, N), float)
    stock_end = np.zeros_like(stock_start)
    gross = np.zeros((T, N), float)
    net_output = np.zeros((T, N), float)
    capc = np.full(T, np.inf)
    labc = np.full(T, np.inf)
    impc = np.full(T, np.inf)
    stock_start[0] = data.initial_stock
    for t in range(T):
        if t > 0:
            stock_start[t] = stock_end[t - 1]
        gs = data.L_by_year[t] @ data.goals[t]
        gi = data.L_by_year[t] @ p[t]
        gross[t] = f[t] * gs + gi
        if cap_mode == 'cell':
            limits = []
            for j in range(N):
                mask = data.C[:, j] > 1e-12
                if not np.any(mask) or gs[j] <= 1e-12:
                    continue
                clim = float(np.min(stock_start[t, mask, j] / data.C[mask, j]))
                limits.append((clim - gi[j]) / gs[j])
            capc[t] = float(min(limits)) if limits else np.inf
        else:
            limits = []
            for j in range(N):
                if Ctotal[t, j] <= 1e-12 or gs[j] <= 1e-12:
                    continue
                clim = float(stock_start[t, :, j].sum() / Ctotal[t, j])
                limits.append((clim - gi[j]) / gs[j])
            capc[t] = float(min(limits)) if limits else np.inf
        ls = float(data.labour_coeff_by_year[t] @ gs)
        li = float(data.labour_coeff_by_year[t] @ gi)
        labc[t] = (data.labour_available[t] - li) / ls if ls > 1e-12 else np.inf
        ims = trade.import_A_by_year[t] @ gs
        imi = trade.import_A_by_year[t] @ gi
        ib = np.divide(trade.import_cap_by_year[t] - imi, ims,
                       out=np.full(N, np.inf), where=ims > 1e-12)
        impc[t] = float(np.min(ib))
        stock_end[t] = stock_start[t] * (1.0 - data.dep_by_year[t]) + investments[t]
        net_output[t] = (np.eye(N) - data.A_by_year[t]) @ gross[t]

    constraint_audit = _build_constraint_audit(
        data,
        trade,
        f=f,
        p=p,
        investments=investments,
        stock_start=stock_start,
        stock_end=stock_end,
        gross=gross,
        net_output=net_output,
        Ctotal=Ctotal,
        cap_mode=cap_mode,
    )
    failed_years = [report.year for report in constraint_audit if not report.compliant]
    if failed_years:
        raise RuntimeError(f'{label} failed corrected constraint audit in years {failed_years}')
    if abs(float(investments[-1].sum())) > AUDIT_ATOL:
        raise RuntimeError(f'{label} has investment in the final shadow year')

    pub = slice(0, published_years)
    return LPResult(
        label=label, mode=data.mode, years=data.years, published_years=published_years,
        theta=float(z[ix['theta']]), f=f, investments=investments, p=p,
        stock_start=stock_start, stock_end=stock_end, gross_realized=gross,
        net_output=net_output,
        mean_harmony_published=harmony_mean(f[pub]),
        min_fulfillment_published=float(np.min(f[pub])),
        mean_harmony_all=harmony_mean(f), min_fulfillment_all=float(np.min(f)),
        investment_published=float(investments[pub].sum()),
        investment_all=float(investments.sum()),
        stock_terminal_published=float(stock_end[published_years - 1].sum()),
        stock_terminal_all=float(stock_end[-1].sum()),
        capital_constraint=capc, labour_constraint=labc, import_constraint=impc,
        constraint_audit=constraint_audit,
        stage1_status=r1.message, stage2_status=r2.message, stage3_status=stage3_status
    )


def scenario_metrics_from_eplus1(label: str, data: c.ModelData, scenario: d.DScenario,
                                 stop: str, ntransfers: int) -> dict:
    return {
        'variant': label, 'technology_mode': data.mode,
        'min_fulfillment_2019_2023': float(np.min(scenario.feasible_ratio)),
        'mean_harmony_2019_2023': float(scenario.mean_harmony),
        'investment_2019_2023_real_musd': float(scenario.investments.sum()),
        'stock_end_2023_real_musd': float(scenario.stock_end[-1].sum()),
        'investment_over_bea_2019_2023': float(scenario.investments.sum() / sum(data.observed_investment[y].sum() for y in data.years)),
        'stock_end_2023_over_bea': float(scenario.stock_end[-1].sum() / data.observed_stock[2023].sum()),
        'computational_min_fulfillment': float(np.min(scenario.feasible_ratio)),
        'computational_mean_harmony': float(scenario.mean_harmony),
        'investment_all_horizon_real_musd': float(scenario.investments.sum()),
        'stock_terminal_all_real_musd': float(scenario.stock_end[-1].sum()),
        'stop_or_status': stop,
        'capital_transfers_or_stage': ntransfers,
    }


def metrics_from_lp(data5: c.ModelData, result: LPResult) -> dict:
    obs_i = float(sum(data5.observed_investment[y].sum() for y in data5.years))
    obs_k = float(data5.observed_stock[2023].sum())
    return {
        'variant': result.label, 'technology_mode': result.mode,
        'min_fulfillment_2019_2023': result.min_fulfillment_published,
        'mean_harmony_2019_2023': result.mean_harmony_published,
        'investment_2019_2023_real_musd': result.investment_published,
        'stock_end_2023_real_musd': result.stock_terminal_published,
        'investment_over_bea_2019_2023': result.investment_published / obs_i,
        'stock_end_2023_over_bea': result.stock_terminal_published / obs_k,
        'computational_min_fulfillment': result.min_fulfillment_all,
        'computational_mean_harmony': result.mean_harmony_all,
        'investment_all_horizon_real_musd': result.investment_all,
        'stock_terminal_all_real_musd': result.stock_terminal_all,
        'stop_or_status': result.stage3_status,
        'capital_transfers_or_stage': 3,
    }


def export_lp_detail(result: LPResult, data5: c.ModelData, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / 'annual_path.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['year','published','fulfillment','harmony','capital_constraint','labour_constraint','import_constraint','investment_real_musd','stock_start_real_musd','stock_end_real_musd','gross_realized_real_musd'])
        for t, y in enumerate(result.years):
            w.writerow([y, int(t < result.published_years), result.f[t], float(c.harmony(result.f[t])),
                        result.capital_constraint[t], result.labour_constraint[t], result.import_constraint[t],
                        float(result.investments[t].sum()), float(result.stock_start[t].sum()),
                        float(result.stock_end[t].sum()), float(result.gross_realized[t].sum())])
    with open(outdir / 'constraint_audit.csv', 'w', newline='', encoding='utf-8') as f:
        rows = [asdict(report) for report in result.constraint_audit]
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    meta = {
        'variant': result.label, 'technology_mode': result.mode,
        'published_years': result.published_years, 'computational_years': result.years,
        'theta': result.theta, 'min_fulfillment_published': result.min_fulfillment_published,
        'mean_harmony_published': result.mean_harmony_published,
        'min_fulfillment_all': result.min_fulfillment_all,
        'mean_harmony_all': result.mean_harmony_all,
        'investment_published_real_musd': result.investment_published,
        'investment_all_real_musd': result.investment_all,
        'stock_terminal_published_real_musd': result.stock_terminal_published,
        'stock_terminal_all_real_musd': result.stock_terminal_all,
        'stage1_status': result.stage1_status,
        'stage2_status': result.stage2_status,
        'stage3_status': result.stage3_status,
        'all_constraint_reports_compliant': all(r.compliant for r in result.constraint_audit),
        'terminal_treatment': 'three_stationary_shadow_years; final computational investment fixed to zero',
        'terminal_equation_from_e_corrected_applied': False,
    }
    (outdir / 'RUN_METADATA.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')


def run_all(root: Path) -> list[dict]:
    data_dir = root / 'data'
    results = root / 'results'
    results.mkdir(exist_ok=True)
    all_rows: list[dict] = []
    annual_rows: list[dict] = []
    aggregate_rows: list[dict] = []

    for mode in ('frozen', 'historical'):
        data = c.load_model_data(data_dir, mode)
        trade = d.load_trade_inventory(data, data_dir)

        # Corrected Milestone E is the only current baseline.  Its terminal equation
        # belongs to E; final F instead values the boundary with three shadow years.
        e = ec.solve_configuration(data, trade, imports_enabled=True, inventories_enabled=False)
        all_rows.append({
            'variant': 'E_corrected_baseline', 'technology_mode': mode,
            'min_fulfillment_2019_2023': float(np.min(e.final.feasible_ratio)),
            'mean_harmony_2019_2023': float(e.final.mean_harmony),
            'investment_2019_2023_real_musd': float(e.final.investments.sum()),
            'stock_end_2023_real_musd': float(e.final.stock_end[-1].sum()),
            'investment_over_bea_2019_2023': float(e.final.investments.sum() / sum(data.observed_investment[y].sum() for y in data.years)),
            'stock_end_2023_over_bea': float(e.final.stock_end[-1].sum() / data.observed_stock[2023].sum()),
            'computational_min_fulfillment': float(np.min(e.final.feasible_ratio)),
            'computational_mean_harmony': float(e.final.mean_harmony),
            'investment_all_horizon_real_musd': float(e.final.investments.sum()),
            'stock_terminal_all_real_musd': float(e.final.stock_end[-1].sum()),
            'stop_or_status': e.stop_reason_capital,
            'capital_transfers_or_stage': len(e.capital_transfers),
        })

        # Historical E+1 development diagnostic.  It still uses the preserved D
        # proposal generator and is therefore labelled legacy, not as a corrected baseline.
        _, e1, e1log, e1stop = solve_eplus1(data, trade)
        all_rows.append(scenario_metrics_from_eplus1('E+1_legacy_maxmin_diagnostic', data, e1, e1stop, len(e1log)))

        # E+2: exact forward-looking multiperiod envelope, original rigid cell capital.
        e2 = solve_lexicographic_lp(data, trade, label='E+2_forward_cell', cap_mode='cell',
                                    dynamic_historical_C=False, published_years=5,
                                    restrict_asset_sources=False)
        all_rows.append(metrics_from_lp(data, e2))
        export_lp_detail(e2, data, results / 'E+2_forward_cell' / mode)

        # E+3: empirical 71-sector capital is treated as an effective sector bundle.
        # In Historical mode its total K/X coefficient is updated ex post year by year.
        e3 = solve_lexicographic_lp(data, trade, label='E+3_dynamic_bundle', cap_mode='sector_bundle',
                                    dynamic_historical_C=True, published_years=5,
                                    restrict_asset_sources=True)
        all_rows.append(metrics_from_lp(data, e3))
        export_lp_detail(e3, data, results / 'E+3_dynamic_bundle' / mode)

        # Final F Corrected: 5 published years + 3 stationary shadow years.
        md8, tr8 = extend_with_shadows(data, trade, 3)
        e4 = solve_lexicographic_lp(md8, tr8, label='F_corrected_5plus3_shadow', cap_mode='sector_bundle',
                                    dynamic_historical_C=True, published_years=5,
                                    restrict_asset_sources=True)
        all_rows.append(metrics_from_lp(data, e4))
        export_lp_detail(e4, data, results / 'F_corrected_5plus3_shadow' / mode)

        # Final Milestone F is the cumulative E+4 specification.
        final_dir = results / 'F_final' / mode
        export_lp_detail(e4, data, final_dir)

        # Annual comparison rows for all variants.
        variants = {
            'E_corrected_baseline': (data.years, e.final.feasible_ratio, e.final.annual_harmony, e.final.investments,
                                     e.final.stock_end, e.final.gross_realized),
            'E+1_legacy_maxmin_diagnostic': (data.years, e1.feasible_ratio, e1.annual_harmony, e1.investments,
                                             e1.stock_end, e1.gross_realized),
            'E+2_forward_cell': (e2.years, e2.f, c.harmony(e2.f), e2.investments, e2.stock_end, e2.gross_realized),
            'E+3_dynamic_bundle': (e3.years, e3.f, c.harmony(e3.f), e3.investments, e3.stock_end, e3.gross_realized),
            'F_corrected_5plus3_shadow': (e4.years, e4.f, c.harmony(e4.f), e4.investments, e4.stock_end, e4.gross_realized),
        }
        for label, (yrs, fv, hv, iv, sv, gv) in variants.items():
            for t, y in enumerate(yrs):
                annual_rows.append({
                    'variant': label, 'technology_mode': mode, 'year': y,
                    'published': int(t < 5), 'fulfillment': float(fv[t]),
                    'harmony': float(hv[t]), 'investment_real_musd': float(iv[t].sum()),
                    'stock_end_real_musd': float(sv[t].sum()),
                    'gross_realized_real_musd': float(gv[t].sum()),
                    'gross_bea_real_musd': float(data.observed_gross[y].sum()) if y in data.observed_gross and y <= 2023 else '',
                })
            model_gross = float(np.asarray(gv[:5]).sum())
            bea_gross = float(sum(data.observed_gross[y].sum() for y in data.years[:5]))
            aggregate_rows.append({
                'variant': label,
                'technology_mode': mode,
                'gross_model_2019_2023_real_musd': model_gross,
                'gross_bea_2019_2023_real_musd': bea_gross,
                'gross_model_over_bea': model_gross / bea_gross,
            })

    # Write headline comparison.
    with open(results / 'VARIANT_COMPARISON.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        w.writeheader(); w.writerows(all_rows)
    with open(results / 'VARIANT_ANNUAL.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(annual_rows[0].keys()))
        w.writeheader(); w.writerows(annual_rows)
    with open(results / 'OUTPUT_AGGREGATE_COMPARISON.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(aggregate_rows[0].keys()))
        w.writeheader(); w.writerows(aggregate_rows)

    final_rows = [r for r in all_rows if r['variant'] == 'F_corrected_5plus3_shadow']
    with open(results / 'F_FINAL_SUMMARY.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(final_rows[0].keys()))
        w.writeheader(); w.writerows(final_rows)

    (results / 'F_SUMMARY.json').write_text(json.dumps({
        'variants': all_rows,
        'final_choice': 'F_corrected_5plus3_shadow',
        'baseline': 'E_corrected_baseline',
        'interpretation': (
            'Milestone F Corrected uses Milestone E Corrected as its empirical baseline, prioritizes '
            'worst-year target fulfillment, retains Harmony as a secondary '
            'criterion, minimizes investment only after those objectives, replaces the empirically '
            'over-rigid cell-by-cell capital minimum with a sector-effective capital bundle at the '
            '71-sector aggregation level, updates total C_t only in the Historical diagnostic mode, '
            'and values terminal capital through three stationary shadow years.'
        )
    }, indent=2), encoding='utf-8')
    return all_rows


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    rows = run_all(root)
    print(json.dumps(rows, indent=2))
