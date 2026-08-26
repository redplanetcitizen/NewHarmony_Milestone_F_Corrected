from __future__ import annotations

"""Machine-readable provenance contract for Milestone F csvplan alignment.

This module does not change the numerical solver.  It records which parts of
Milestone F remain inherited physical/accounting core and which parts are
Milestone-F-specific research extensions.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
import hashlib


CSVPLAN_RECONCILED_COMMIT = "ded576c5b8c80d2bbc9fbf3a8a7a391f0a64a433"
E_NUMERICAL_BASELINE_COMMIT = "3faf1657bf0df93906477ed3ba85766406f323ba"
E_ALIGNMENT_GATE_COMMIT = "eecbc29ec6b82a677545eca4f9540d1623328d98"
F_PRE_ALIGNMENT_COMMIT = "d71a68c6f02cde756ed814b8e209b23177ab56e0"
EXPECTED_EMBEDDED_E_GIT_BLOB = "193fce86af7a7497035bb3407e3ec972a8598bc2"


@dataclass(frozen=True)
class Rule:
    key: str
    status: str
    implementation: str
    provenance: str


RULES = (
    Rule("vector_accounting", "aligned_core", "(I-A_t)x_t = f_t g_t + p_t", "csvplan_reconciled_physical_core"),
    Rule("robust_harmony", "aligned_equivalent_specialization", "common annual plan-ray factor implies common positive-target fulfillment", "csvplan_reconciled_physical_core"),
    Rule("stock_recurrence", "aligned_core", "S_end[t]=S_start[t]*(1-d_t)+I_t", "csvplan_reconciled_physical_core"),
    Rule("cohort_depreciation", "aligned_core_forward_form", "cell-specific survival factors propagate every earlier investment cohort", "csvplan_reconciled_physical_core"),
    Rule("candidate_admissibility", "structural_equivalent", "LP feasibility plus independent annual constraint audit", "csvplan_reconciled_physical_core"),
    Rule("destination_priority", "not_applicable", "all years solved simultaneously", "milestone_f_architecture"),
    Rule("source_year_selection", "not_applicable", "all investment cohorts chosen simultaneously", "milestone_f_architecture"),
    Rule("c26_increment", "not_applicable", "investment quantity is an endogenous LP variable", "milestone_f_architecture"),
    Rule("preliminary_schedule", "milestone_f_architecture_choice", "none; investment variables are endogenous and nonnegative", "milestone_f_preliminary_schedule"),
    Rule("epsilon", "not_applicable", "no iterative transfer step", "milestone_f_architecture"),
    Rule("cv_stopping", "not_applicable", "no CV-based iterative stop", "milestone_f_architecture"),
    Rule("lexicographic_objective", "milestone_f_extension", "maximize min fulfillment, then approximate mean Harmony, then minimize capital-goods output", "milestone_f_objective"),
    Rule("harmony_approximation", "milestone_f_numerical_extension", "81-point tangent upper envelope on 0<=f<=1", "milestone_f_harmony_approximation"),
    Rule("capital_bundle", "milestone_f_empirical_extension", "effective capital bundle by user sector", "milestone_f_capital_representation"),
    Rule("asset_source_restriction", "milestone_f_empirical_extension", "restrict new investment to selected reproducible-asset-producing source sectors", "milestone_f_asset_source_restriction"),
    Rule("historical_dynamic_C", "milestone_f_ex_post_diagnostic", "observed start-stock/output ratios in historical mode", "milestone_f_historical_C"),
    Rule("imports", "inherited_empirical_extension", "componentwise import envelope", "milestone_e_empirical_inheritance"),
    Rule("inventories", "omitted_e_extension", "no inventory-transfer search in final F LP", "milestone_f_architecture"),
    Rule("terminal_boundary", "milestone_f_boundary_extension", "three stationary shadow years; final computational investment fixed to zero", "milestone_f_boundary"),
    Rule("observed_investment", "aligned_empirical_diagnostic", "reported comparison only", "milestone_e_empirical_inheritance"),
)


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def validate_contract(root: Path | None = None) -> None:
    root = root or Path(__file__).resolve().parents[1]
    by_key = {rule.key: rule for rule in RULES}
    if len(by_key) != len(RULES):
        raise AssertionError("duplicate provenance rule key")

    required_core = {"vector_accounting", "robust_harmony", "stock_recurrence", "cohort_depreciation", "candidate_admissibility"}
    for key in required_core:
        if not by_key[key].status.startswith("aligned") and by_key[key].status != "structural_equivalent":
            raise AssertionError(f"{key} is not recorded as inherited/aligned core")

    if by_key["preliminary_schedule"].implementation.lower().startswith("zero warm"):
        raise AssertionError("F must not describe endogenous LP investment as a zero warm start")
    if "endogenous" not in by_key["preliminary_schedule"].implementation.lower():
        raise AssertionError("F preliminary-schedule provenance must state endogenous investment")

    for key in ("destination_priority", "source_year_selection", "c26_increment", "epsilon", "cv_stopping"):
        if by_key[key].status != "not_applicable":
            raise AssertionError(f"iterative controller rule {key} must be not_applicable in final F")

    for key in ("lexicographic_objective", "harmony_approximation", "capital_bundle", "asset_source_restriction", "terminal_boundary"):
        if "milestone_f" not in by_key[key].status:
            raise AssertionError(f"{key} must be explicitly labelled as a Milestone F extension")

    embedded_e = root / "code" / "new_harmony_empirical_e_corrected.py"
    if git_blob_sha(embedded_e) != EXPECTED_EMBEDDED_E_GIT_BLOB:
        raise AssertionError("embedded E solver no longer matches the aligned E numerical solver blob")


def provenance(root: Path | None = None) -> dict:
    root = root or Path(__file__).resolve().parents[1]
    validate_contract(root)
    return {
        "profile": "milestone_f_csvplan_reconciled_alignment",
        "csvplan_reconciled_commit": CSVPLAN_RECONCILED_COMMIT,
        "milestone_e_numerical_baseline_commit": E_NUMERICAL_BASELINE_COMMIT,
        "milestone_e_alignment_gate_commit": E_ALIGNMENT_GATE_COMMIT,
        "milestone_f_pre_alignment_commit": F_PRE_ALIGNMENT_COMMIT,
        "embedded_e_git_blob": git_blob_sha(root / "code" / "new_harmony_empirical_e_corrected.py"),
        "numerical_solver_change_required": False,
        "alignment_scope": "provenance_and_documentation",
        "rules": [asdict(rule) for rule in RULES],
    }
