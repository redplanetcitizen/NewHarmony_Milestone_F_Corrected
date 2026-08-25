from __future__ import annotations

"""Corrected empirical New Harmony solver for Milestone E.

This module preserves the 71-sector empirical extensions of Milestones C/D
while incorporating the ten corrections implemented in ``csvplan_corrected``.
The accepted investment rule remains marginal capacity relief: there is no
70-percent replacement floor or other general maintenance requirement.
"""

from dataclasses import asdict, dataclass, field
from pathlib import Path
import csv
import json
import logging

import numpy as np

import new_harmony_empirical_c as c
import new_harmony_empirical_d as d


LOGGER = logging.getLogger(__name__)
GAIN_TOL = 1.0e-12


class ConstraintViolation(RuntimeError):
    pass


class TerminalConstraintWarning(RuntimeError):
    pass


@dataclass
class SolverConfig:
    harmony_cv_threshold: float = c.DEFAULT_MIN_CV
    max_iterations: int = 3000
    initial_step: float = 0.25
    minimum_step: float = 1.0e-5
    maximum_step: float = 0.5
    step_growth: float = 1.15
    step_shrink: float = 0.5
    tolerance: float = 1.0e-8
    strict: bool = False
    terminal_replacement: bool = True
    verbose: bool = False


@dataclass
class YearConstraintReport:
    year: int
    flow_balance_ok: bool
    labour_ok: bool
    capital_ok: bool
    imports_ok: bool
    consumption_ok: bool
    inventory_ok: bool
    max_flow_residual: float
    labour_used: float
    labour_available: float
    max_capital_excess: float
    max_import_excess: float
    min_consumption: float
    min_inventory: float

    @property
    def compliant(self) -> bool:
        return (
            self.flow_balance_ok
            and self.labour_ok
            and self.capital_ok
            and self.imports_ok
            and self.consumption_ok
            and self.inventory_ok
        )


@dataclass
class TerminalStatus:
    enabled: bool = False
    q: float = 0.0
    q_labour: float = np.inf
    q_capital: float = np.inf
    q_imports: float = np.inf
    binding_constraint: str = "disabled"
    nonlabour_limited: bool = False


@dataclass
class CorrectedScenario:
    investments: np.ndarray
    inventory_transfers: np.ndarray
    stock_start: np.ndarray
    stock_end: np.ndarray
    gross_required: np.ndarray
    gross_realized: np.ndarray
    total_final_required: np.ndarray
    net_social_output: np.ndarray
    fulfillment: np.ndarray
    harmony_by_product: np.ndarray
    annual_harmony: np.ndarray
    mean_harmony: float
    std_harmony: float
    cv_harmony: float
    objective: float
    capital_constraint: np.ndarray
    labour_constraint: np.ndarray
    import_constraint: np.ndarray
    production_scale: np.ndarray
    raw_production_scale: np.ndarray
    feasible_ratio: np.ndarray
    imported_intermediate_required: np.ndarray
    imported_intermediate_cap: np.ndarray
    inventory_accumulation: np.ndarray
    inventory_release: np.ndarray
    inventory_start: np.ndarray
    inventory_end: np.ndarray
    constraint_report: list[YearConstraintReport] = field(default_factory=list)
    terminal_status: TerminalStatus = field(default_factory=TerminalStatus)


@dataclass
class CorrectedSolveResult:
    initial: CorrectedScenario
    final: CorrectedScenario
    capital_transfers: list[dict]
    inventory_transfers_log: list[dict]
    stop_reason_capital: str
    stop_reason_inventory: str
    capital_iterations: int
    inventory_iterations: int
    objective_history: list[float] = field(default_factory=list)
    step_history: list[float] = field(default_factory=list)


def _validate_inventory_tensor(transfers: np.ndarray, T: int, N: int, tolerance: float) -> None:
    if transfers.shape != (T, T, N) or not np.isfinite(transfers).all():
        raise ValueError("inventory transfers must be a finite T x T x N tensor")
    if np.any(transfers < -tolerance):
        raise ValueError("inventory transfers must be nonnegative")
    for source in range(T):
        if np.any(transfers[source, : source + 1] > tolerance):
            raise ValueError("inventory transfers must be strictly forward in time")


def _stock_path(data: c.ModelData, investments: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    T, N = data.goals.shape
    start = np.zeros((T, N, N), dtype=float)
    end = np.zeros_like(start)
    start[0] = data.initial_stock
    for t in range(T):
        if t:
            start[t] = end[t - 1]
        end[t] = start[t] * (1.0 - data.dep_by_year[t]) + investments[t]
    return start, end


def inverse_depreciate_gap(
    gap: np.ndarray, data: c.ModelData, source: int, destination: int
) -> np.ndarray:
    """Undo cell-specific annual depreciation between source and destination."""
    if not 0 <= source < destination:
        raise ValueError("source year must precede destination year")
    survival = np.ones_like(gap, dtype=float)
    for year in range(source + 1, destination):
        survival *= 1.0 - data.dep_by_year[year]
    return np.divide(
        gap,
        survival,
        out=np.full_like(gap, np.inf, dtype=float),
        where=survival > 1.0e-12,
    )


def terminal_replacement(
    data: c.ModelData,
    trade: d.TradeInventoryData,
    stock: np.ndarray,
    *,
    imports_enabled: bool,
    config: SolverConfig,
) -> tuple[np.ndarray, TerminalStatus]:
    """Implement x=(I-A_T-D_T)^-1(q*g_T) without a general maintenance floor."""
    t = len(data.years) - 1
    D_t = data.C * data.dep_by_year[t]
    system = np.eye(len(data.sectors)) - data.A_by_year[t] - D_t
    try:
        base_gross = np.linalg.solve(system, data.goals[t])
    except np.linalg.LinAlgError as exc:
        raise ConstraintViolation("terminal matrix I-A-D is singular") from exc
    if not np.isfinite(base_gross).all() or np.min(base_gross) < -config.tolerance:
        raise ConstraintViolation("terminal equation has a non-finite or negative gross-output solution")
    base_gross = np.maximum(base_gross, 0.0)

    labour_base = float(data.labour_coeff_by_year[t] @ base_gross)
    q_labour = np.inf if labour_base <= config.tolerance else float(data.labour_available[t] / labour_base)

    required_base = data.C * base_gross[None, :]
    mask = required_base > config.tolerance
    q_capital = float(np.min(stock[mask] / required_base[mask])) if np.any(mask) else np.inf

    if imports_enabled:
        imported_base = trade.import_A_by_year[t] @ base_gross
        mask_import = imported_base > config.tolerance
        q_imports = (
            float(np.min(trade.import_cap_by_year[t, mask_import] / imported_base[mask_import]))
            if np.any(mask_import)
            else np.inf
        )
    else:
        q_imports = np.inf

    limits = {"labour": q_labour, "capital": q_capital, "imports": q_imports}
    binding = min(limits, key=limits.get)
    q = max(0.0, float(limits[binding]))
    if not np.isfinite(q):
        raise ConstraintViolation("terminal output scale is unbounded")
    nonlabour_limited = binding != "labour" and q + config.tolerance < q_labour
    if nonlabour_limited:
        message = (
            f"terminal year {data.years[t]} is {binding}-limited: "
            f"q={q:.9g}, labour would permit q={q_labour:.9g}"
        )
        if config.strict:
            raise TerminalConstraintWarning(message)

    gross = q * base_gross
    replacement = D_t * gross[None, :]
    return replacement, TerminalStatus(
        enabled=True,
        q=q,
        q_labour=q_labour,
        q_capital=q_capital,
        q_imports=q_imports,
        binding_constraint=binding,
        nonlabour_limited=nonlabour_limited,
    )


def _year_report(
    data: c.ModelData,
    trade: d.TradeInventoryData,
    scenario: CorrectedScenario,
    t: int,
    *,
    imports_enabled: bool,
    tolerance: float,
) -> YearConstraintReport:
    gross = scenario.gross_realized[t]
    investment = scenario.investments[t].sum(axis=1)
    accumulation = scenario.inventory_accumulation[t]
    release = scenario.inventory_release[t]
    rhs = scenario.net_social_output[t] + investment + accumulation - release
    residual = (np.eye(len(data.sectors)) - data.A_by_year[t]) @ gross - rhs
    flow_scale = max(1.0, float(np.max(np.abs(rhs))))
    max_flow_residual = float(np.max(np.abs(residual)))

    labour_used = float(data.labour_coeff_by_year[t] @ gross)
    labour_tolerance = tolerance * max(1.0, float(data.labour_available[t]))
    capital_excess = data.C * gross[None, :] - scenario.stock_start[t]
    capital_tolerance = tolerance * max(1.0, float(np.max(scenario.stock_start[t])))
    max_capital_excess = float(np.max(capital_excess))

    if imports_enabled:
        import_excess = scenario.imported_intermediate_required[t] - scenario.imported_intermediate_cap[t]
        import_tolerance = tolerance * max(1.0, float(np.max(scenario.imported_intermediate_cap[t])))
        max_import_excess = float(np.max(import_excess))
        imports_ok = max_import_excess <= import_tolerance
    else:
        max_import_excess = float("-inf")
        imports_ok = True

    min_consumption = float(np.min(scenario.net_social_output[t]))
    min_inventory = float(np.min(scenario.inventory_end[t]))
    return YearConstraintReport(
        year=int(data.years[t]),
        flow_balance_ok=max_flow_residual <= tolerance * flow_scale,
        labour_ok=labour_used <= data.labour_available[t] + labour_tolerance,
        capital_ok=max_capital_excess <= capital_tolerance,
        imports_ok=imports_ok,
        consumption_ok=min_consumption >= -tolerance,
        inventory_ok=min_inventory >= -tolerance,
        max_flow_residual=max_flow_residual,
        labour_used=labour_used,
        labour_available=float(data.labour_available[t]),
        max_capital_excess=max_capital_excess,
        max_import_excess=max_import_excess,
        min_consumption=min_consumption,
        min_inventory=min_inventory,
    )


def evaluate(
    data: c.ModelData,
    trade: d.TradeInventoryData,
    investments: np.ndarray,
    inventory_transfers: np.ndarray | None = None,
    *,
    imports_enabled: bool = True,
    inventories_enabled: bool = False,
    config: SolverConfig | None = None,
) -> CorrectedScenario:
    config = config or SolverConfig()
    T, N = data.goals.shape
    investments = np.asarray(investments, dtype=float).copy()
    if investments.shape != (T, N, N) or not np.isfinite(investments).all():
        raise ValueError("investment tensor must be finite and T x N x N")
    if np.any(investments < -config.tolerance):
        raise ValueError("investment tensor must be nonnegative")

    if inventory_transfers is None or not inventories_enabled:
        inventory_transfers = np.zeros((T, T, N), dtype=float)
    else:
        inventory_transfers = np.asarray(inventory_transfers, dtype=float).copy()
    _validate_inventory_tensor(inventory_transfers, T, N, config.tolerance)
    accumulation = inventory_transfers.sum(axis=1)
    release = inventory_transfers.sum(axis=0)
    if np.any(release - data.goals > config.tolerance):
        raise ConstraintViolation("inventory release exceeds the corresponding social target")

    terminal_status = TerminalStatus()
    if config.terminal_replacement:
        investments[-1] = 0.0
        stock_start, stock_end = _stock_path(data, investments)
        investments[-1], terminal_status = terminal_replacement(
            data,
            trade,
            stock_start[-1],
            imports_enabled=imports_enabled,
            config=config,
        )
    stock_start, stock_end = _stock_path(data, investments)

    gross_required = np.zeros((T, N), dtype=float)
    gross_realized = np.zeros_like(gross_required)
    total_final_required = np.zeros_like(gross_required)
    net_social_output = np.zeros_like(gross_required)
    fulfillment = np.full_like(gross_required, np.nan)
    harmony_by_product = np.full_like(gross_required, np.nan)
    annual_harmony = np.zeros(T, dtype=float)
    capital_constraint = np.full(T, np.inf)
    labour_constraint = np.full(T, np.inf)
    import_constraint = np.full(T, np.inf)
    production_scale = np.zeros(T, dtype=float)
    raw_production_scale = np.zeros(T, dtype=float)
    feasible_ratio = np.zeros(T, dtype=float)
    imported_required = np.zeros((T, N), dtype=float)
    imported_cap = np.full((T, N), np.inf)
    inventory_start = np.zeros((T, N), dtype=float)
    inventory_end = np.zeros((T, N), dtype=float)

    for t in range(T):
        if t:
            inventory_start[t] = inventory_end[t - 1]
        residual_goal = np.maximum(data.goals[t] - release[t], 0.0)
        investment_vector = investments[t].sum(axis=1)
        fixed_final = investment_vector + accumulation[t]
        total_final_required[t] = residual_goal + fixed_final
        gross_social = data.L_by_year[t] @ residual_goal
        gross_fixed = data.L_by_year[t] @ fixed_final
        gross_required[t] = gross_social + gross_fixed

        bounds: list[float] = []
        fixed_feasible = True
        capital_base = data.C * gross_fixed[None, :]
        capital_slope = data.C * gross_social[None, :]
        if np.any(capital_base - stock_start[t] > config.tolerance):
            fixed_feasible = False
        mask_capital = capital_slope > config.tolerance
        if np.any(mask_capital):
            cap_bounds = (stock_start[t][mask_capital] - capital_base[mask_capital]) / capital_slope[mask_capital]
            capital_constraint[t] = float(np.min(cap_bounds))
            bounds.append(capital_constraint[t])

        labour_fixed = float(data.labour_coeff_by_year[t] @ gross_fixed)
        labour_social = float(data.labour_coeff_by_year[t] @ gross_social)
        if labour_fixed > data.labour_available[t] + config.tolerance:
            fixed_feasible = False
        if labour_social > config.tolerance:
            labour_constraint[t] = float((data.labour_available[t] - labour_fixed) / labour_social)
            bounds.append(labour_constraint[t])

        if imports_enabled:
            import_fixed = trade.import_A_by_year[t] @ gross_fixed
            import_social = trade.import_A_by_year[t] @ gross_social
            imported_cap[t] = trade.import_cap_by_year[t]
            if np.any(import_fixed - imported_cap[t] > config.tolerance):
                fixed_feasible = False
            mask_import = import_social > config.tolerance
            if np.any(mask_import):
                import_bounds = (imported_cap[t, mask_import] - import_fixed[mask_import]) / import_social[mask_import]
                import_constraint[t] = float(np.min(import_bounds))
                bounds.append(import_constraint[t])

        if not bounds:
            raise ConstraintViolation(f"year {data.years[t]} has no finite resource bound")
        raw_scale = float(min(bounds))
        if not fixed_feasible:
            raw_scale = min(raw_scale, -1.0)
        raw_production_scale[t] = raw_scale
        production_scale[t] = max(0.0, raw_scale)
        gross_realized[t] = gross_fixed + production_scale[t] * gross_social
        if imports_enabled:
            imported_required[t] = trade.import_A_by_year[t] @ gross_realized[t]

        produced_final = (np.eye(N) - data.A_by_year[t]) @ gross_realized[t]
        consumption = produced_final - investment_vector - accumulation[t] + release[t]
        net_social_output[t] = consumption
        positive_targets = data.goals[t] > config.tolerance
        if not np.any(positive_targets):
            raise ConstraintViolation(f"year {data.years[t]} has no positive social target")
        ratios = consumption[positive_targets] / data.goals[t, positive_targets]
        fulfillment[t, positive_targets] = ratios
        harmony_by_product[t, positive_targets] = c.harmony(ratios)
        feasible_ratio[t] = float(np.min(ratios))
        annual_harmony[t] = float(np.min(harmony_by_product[t, positive_targets]))

        inventory_end[t] = inventory_start[t] + accumulation[t] - release[t]

    mean_harmony = float(np.mean(annual_harmony))
    std_harmony = float(np.std(annual_harmony, ddof=1)) if T > 1 else 0.0
    cv_harmony = std_harmony / abs(mean_harmony) if mean_harmony else np.inf
    scenario = CorrectedScenario(
        investments=investments,
        inventory_transfers=inventory_transfers,
        stock_start=stock_start,
        stock_end=stock_end,
        gross_required=gross_required,
        gross_realized=gross_realized,
        total_final_required=total_final_required,
        net_social_output=net_social_output,
        fulfillment=fulfillment,
        harmony_by_product=harmony_by_product,
        annual_harmony=annual_harmony,
        mean_harmony=mean_harmony,
        std_harmony=std_harmony,
        cv_harmony=cv_harmony,
        objective=float(np.sum(annual_harmony)),
        capital_constraint=capital_constraint,
        labour_constraint=labour_constraint,
        import_constraint=import_constraint,
        production_scale=production_scale,
        raw_production_scale=raw_production_scale,
        feasible_ratio=feasible_ratio,
        imported_intermediate_required=imported_required,
        imported_intermediate_cap=imported_cap,
        inventory_accumulation=accumulation,
        inventory_release=release,
        inventory_start=inventory_start,
        inventory_end=inventory_end,
        terminal_status=terminal_status,
    )
    scenario.constraint_report = [
        _year_report(
            data,
            trade,
            scenario,
            t,
            imports_enabled=imports_enabled,
            tolerance=config.tolerance,
        )
        for t in range(T)
    ]
    failures = [report.year for report in scenario.constraint_report if not report.compliant]
    if failures and config.strict:
        raise ConstraintViolation(f"scenario violates constraints in years {failures}")
    return scenario


def _capital_gap_for_scale(
    data: c.ModelData,
    scenario: CorrectedScenario,
    destination: int,
    target_scale: float,
) -> tuple[np.ndarray, np.ndarray]:
    release = scenario.inventory_release[destination]
    accumulation = scenario.inventory_accumulation[destination]
    residual_goal = np.maximum(data.goals[destination] - release, 0.0)
    investment_vector = scenario.investments[destination].sum(axis=1)
    desired_final = target_scale * residual_goal + investment_vector + accumulation
    gross_desired = data.L_by_year[destination] @ desired_final
    required = data.C * gross_desired[None, :]
    return gross_desired, np.maximum(required - scenario.stock_start[destination], 0.0)


def _candidate_for_destination(
    data: c.ModelData,
    trade: d.TradeInventoryData,
    scenario: CorrectedScenario,
    destination: int,
    step: float,
    *,
    imports_enabled: bool,
    config: SolverConfig,
) -> tuple[CorrectedScenario | None, int | None, np.ndarray | None, float, float]:
    target_scale = float(c.harmony_inverse(scenario.mean_harmony))
    current_scale = float(scenario.feasible_ratio[destination])
    if target_scale <= current_scale + config.tolerance:
        return None, None, None, current_scale, current_scale
    attempted_scale = current_scale + step * (target_scale - current_scale)
    _, gap = _capital_gap_for_scale(data, scenario, destination, attempted_scale)
    if not np.isfinite(gap).all() or float(np.max(gap)) <= config.tolerance:
        return None, None, None, current_scale, attempted_scale

    best: CorrectedScenario | None = None
    best_source: int | None = None
    best_investment: np.ndarray | None = None
    for source in range(destination):
        source_investment = inverse_depreciate_gap(gap, data, source, destination)
        if not np.isfinite(source_investment).all():
            continue
        proposal = scenario.investments.copy()
        proposal[source] += source_investment
        try:
            candidate = evaluate(
                data,
                trade,
                proposal,
                scenario.inventory_transfers,
                imports_enabled=imports_enabled,
                inventories_enabled=False,
                config=config,
            )
        except (ConstraintViolation, TerminalConstraintWarning, np.linalg.LinAlgError, ValueError):
            continue
        if not all(report.compliant for report in candidate.constraint_report):
            continue
        if candidate.objective <= scenario.objective + config.tolerance:
            continue
        if best is None or candidate.objective > best.objective:
            best = candidate
            best_source = source
            best_investment = source_investment
    return best, best_source, best_investment, current_scale, attempted_scale


def solve_capital(
    data: c.ModelData,
    trade: d.TradeInventoryData,
    *,
    imports_enabled: bool = True,
    config: SolverConfig | None = None,
    initial_investments: np.ndarray | None = None,
) -> tuple[CorrectedScenario, CorrectedScenario, list[dict], str, int, list[float], list[float]]:
    config = config or SolverConfig()
    if config.verbose:
        logging.basicConfig(level=logging.INFO)
    T, N = data.goals.shape
    investments = (
        np.zeros((T, N, N), dtype=float)
        if initial_investments is None
        else np.asarray(initial_investments, dtype=float).copy()
    )
    inventory = np.zeros((T, T, N), dtype=float)
    current = evaluate(
        data,
        trade,
        investments,
        inventory,
        imports_enabled=imports_enabled,
        inventories_enabled=False,
        config=config,
    )
    initial = current
    transfers: list[dict] = []
    objective_history = [current.objective]
    step_history: list[float] = []
    step = config.initial_step

    for iteration in range(1, config.max_iterations + 1):
        if current.cv_harmony < config.harmony_cv_threshold:
            return initial, current, transfers, "cv_threshold", iteration - 1, objective_history, step_history

        accepted = None
        accepted_source = None
        accepted_destination = None
        accepted_amount = None
        accepted_current_scale = 0.0
        accepted_attempted_scale = 0.0
        trial_step = step
        while trial_step >= config.minimum_step and accepted is None:
            eligible = sorted(range(1, T), key=lambda year: current.annual_harmony[year])
            for destination in eligible:
                candidate, source, amount, current_scale, attempted_scale = _candidate_for_destination(
                    data,
                    trade,
                    current,
                    destination,
                    trial_step,
                    imports_enabled=imports_enabled,
                    config=config,
                )
                if candidate is not None:
                    accepted = candidate
                    accepted_source = source
                    accepted_destination = destination
                    accepted_amount = amount
                    accepted_current_scale = current_scale
                    accepted_attempted_scale = attempted_scale
                    break
            if accepted is None:
                trial_step *= config.step_shrink

        if accepted is None:
            return initial, current, transfers, "minimum_step", iteration - 1, objective_history, step_history

        old_objective = current.objective
        old_mean = current.mean_harmony
        gain = accepted.objective - old_objective
        if gain <= config.tolerance:
            raise ConstraintViolation("accepted capital proposal did not improve total Harmony")
        by_source = accepted_amount.sum(axis=1)
        by_destination = accepted_amount.sum(axis=0)
        top_sources = np.argsort(by_source)[::-1][:5]
        top_destinations = np.argsort(by_destination)[::-1][:5]
        transfers.append(
            {
                "iteration": iteration,
                "technology_mode": data.mode,
                "source_year": data.years[accepted_source],
                "destination_year": data.years[accepted_destination],
                "mean_harmony_before": current.mean_harmony,
                "mean_harmony_after": accepted.mean_harmony,
                "objective_before": old_objective,
                "objective_after": accepted.objective,
                "gain": gain,
                "cv_before": current.cv_harmony,
                "cv_after": accepted.cv_harmony,
                "destination_harmony_before": current.annual_harmony[accepted_destination],
                "destination_harmony_after": accepted.annual_harmony[accepted_destination],
                "current_worst_fulfillment": accepted_current_scale,
                "desired_worst_fulfillment": accepted_attempted_scale,
                "step": trial_step,
                "investment_at_source_real_musd": float(accepted_amount.sum()),
                "top_capital_sources": "; ".join(
                    f"{data.sectors[i]}:{by_source[i]:.3f}" for i in top_sources if by_source[i] > 0
                ),
                "top_capacity_destinations": "; ".join(
                    f"{data.sectors[i]}:{by_destination[i]:.3f}"
                    for i in top_destinations
                    if by_destination[i] > 0
                ),
            }
        )
        current = accepted
        objective_history.append(current.objective)
        step_history.append(trial_step)
        oscillating = current.annual_harmony[accepted_destination] > old_mean + config.tolerance
        if oscillating:
            step = max(config.minimum_step, trial_step * config.step_shrink)
        else:
            step = min(config.maximum_step, trial_step * config.step_growth)

    return initial, current, transfers, "max_iterations", config.max_iterations, objective_history, step_history


def balance_inventories(
    data: c.ModelData,
    trade: d.TradeInventoryData,
    capital_scenario: CorrectedScenario,
    *,
    imports_enabled: bool,
    config: SolverConfig,
) -> tuple[CorrectedScenario, np.ndarray, list[dict], str, int]:
    T, N = data.goals.shape
    tensor = np.zeros((T, T, N), dtype=float)
    current = evaluate(
        data,
        trade,
        capital_scenario.investments,
        tensor,
        imports_enabled=imports_enabled,
        inventories_enabled=True,
        config=config,
    )
    logs: list[dict] = []
    step = config.initial_step
    envelope = trade.inventory_flow_envelope

    for iteration in range(1, config.max_iterations + 1):
        if current.cv_harmony < config.harmony_cv_threshold:
            return current, tensor, logs, "cv_threshold", iteration - 1
        accepted = None
        trial_step = step
        accepted_meta = None
        while trial_step >= config.minimum_step and accepted is None:
            for destination in sorted(range(1, T), key=lambda year: current.annual_harmony[year]):
                target_scale = float(c.harmony_inverse(current.mean_harmony))
                current_scale = float(current.feasible_ratio[destination])
                difference = max(0.0, target_scale - current_scale)
                if difference <= config.tolerance:
                    continue
                net = current.inventory_accumulation - current.inventory_release
                best_for_destination = None
                for source in range(destination):
                    source_used = np.maximum(net[source], 0.0)
                    destination_used = np.maximum(-net[destination], 0.0)
                    for product in range(N):
                        if data.goals[destination, product] <= config.tolerance:
                            continue
                        amount = min(
                            difference * trial_step * data.goals[destination, product],
                            max(0.0, envelope[source, product] - source_used[product]),
                            max(0.0, envelope[destination, product] - destination_used[product]),
                            max(0.0, data.goals[destination, product] - current.inventory_release[destination, product]),
                        )
                        if amount <= config.tolerance:
                            continue
                        proposal = tensor.copy()
                        proposal[source, destination, product] += amount
                        try:
                            candidate = evaluate(
                                data,
                                trade,
                                capital_scenario.investments,
                                proposal,
                                imports_enabled=imports_enabled,
                                inventories_enabled=True,
                                config=config,
                            )
                        except (ConstraintViolation, TerminalConstraintWarning, ValueError, np.linalg.LinAlgError):
                            continue
                        if not all(report.compliant for report in candidate.constraint_report):
                            continue
                        gain = candidate.objective - current.objective
                        if gain <= config.tolerance:
                            continue
                        if best_for_destination is None or gain > best_for_destination[0]:
                            best_for_destination = (gain, candidate, proposal, source, destination, product, amount)
                if best_for_destination is not None:
                    accepted_meta = best_for_destination
                    accepted = best_for_destination[1]
                    break
            if accepted is None:
                trial_step *= config.step_shrink

        if accepted is None:
            return current, tensor, logs, "minimum_step", iteration - 1
        gain, accepted, tensor, source, destination, product, amount = accepted_meta
        old_mean = current.mean_harmony
        logs.append(
            {
                "iteration": iteration,
                "technology_mode": data.mode,
                "source_year": data.years[source],
                "destination_year": data.years[destination],
                "bea_code": data.sectors[product],
                "sector_name": data.names[data.sectors[product]],
                "amount_real_2019price_musd": float(amount),
                "objective_before": current.objective,
                "objective_after": accepted.objective,
                "gain": gain,
                "step": trial_step,
            }
        )
        current = accepted
        if current.annual_harmony[destination] > old_mean + config.tolerance:
            step = max(config.minimum_step, trial_step * config.step_shrink)
        else:
            step = min(config.maximum_step, trial_step * config.step_growth)

    return current, tensor, logs, "max_iterations", config.max_iterations


def solve_configuration(
    data: c.ModelData,
    trade: d.TradeInventoryData,
    *,
    imports_enabled: bool,
    inventories_enabled: bool,
    config: SolverConfig | None = None,
    legacy_replay: bool = False,
) -> CorrectedSolveResult | d.DSolveResult:
    if legacy_replay:
        return d.solve_configuration(
            data,
            trade,
            imports_enabled=imports_enabled,
            inventories_enabled=inventories_enabled,
        )
    config = config or SolverConfig()
    initial, capital_final, capital_log, capital_stop, capital_iterations, objectives, steps = solve_capital(
        data,
        trade,
        imports_enabled=imports_enabled,
        config=config,
    )
    if inventories_enabled:
        final, _, inventory_log, inventory_stop, inventory_iterations = balance_inventories(
            data,
            trade,
            capital_final,
            imports_enabled=imports_enabled,
            config=config,
        )
    else:
        final = capital_final
        inventory_log = []
        inventory_stop = "disabled"
        inventory_iterations = 0
    result = CorrectedSolveResult(
        initial=initial,
        final=final,
        capital_transfers=capital_log,
        inventory_transfers_log=inventory_log,
        stop_reason_capital=capital_stop,
        stop_reason_inventory=inventory_stop,
        capital_iterations=capital_iterations,
        inventory_iterations=inventory_iterations,
        objective_history=objectives,
        step_history=steps,
    )
    terminal = result.final.terminal_status
    if terminal.nonlabour_limited:
        LOGGER.warning(
            "terminal year %s is %s-limited: q=%.9g, labour would permit q=%.9g",
            data.years[-1],
            terminal.binding_constraint,
            terminal.q,
            terminal.q_labour,
        )
    return result


def solve_capital_from_initial(
    data: c.ModelData,
    trade: d.TradeInventoryData,
    initial_investments: np.ndarray,
    *,
    imports_enabled: bool = True,
    config: SolverConfig | None = None,
) -> CorrectedScenario:
    _, final, _, _, _, _, _ = solve_capital(
        data,
        trade,
        imports_enabled=imports_enabled,
        config=config,
        initial_investments=initial_investments,
    )
    return final


def export_result(
    data: c.ModelData,
    trade: d.TradeInventoryData,
    result: CorrectedSolveResult,
    outdir: Path,
    *,
    imports_enabled: bool,
    inventories_enabled: bool,
) -> None:
    d.export_result(
        data,
        trade,
        result,
        outdir,
        imports_enabled=imports_enabled,
        inventories_enabled=inventories_enabled,
    )
    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / "constraint_audit.csv", "w", newline="", encoding="utf-8") as stream:
        rows = []
        for report in result.final.constraint_report:
            row = asdict(report)
            row["compliant"] = report.compliant
            rows.append(row)
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with open(outdir / "harmony_by_product.csv", "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["year", "bea_code", "sector_name", "target", "net_social_output", "fulfillment", "harmony"])
        for t, year in enumerate(data.years):
            for i, code in enumerate(data.sectors):
                writer.writerow(
                    [
                        year,
                        code,
                        data.names[code],
                        data.goals[t, i],
                        result.final.net_social_output[t, i],
                        result.final.fulfillment[t, i],
                        result.final.harmony_by_product[t, i],
                    ]
                )
    metadata_path = outdir / "RUN_METADATA.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update(
        {
            "solver": "new_harmony_empirical_e_corrected",
            "corrected_rules": 10,
            "replacement_floor": 0.0,
            "terminal_status": asdict(result.final.terminal_status),
            "objective_history": result.objective_history,
            "step_history": result.step_history,
            "all_constraint_reports_compliant": all(r.compliant for r in result.final.constraint_report),
        }
    )
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
