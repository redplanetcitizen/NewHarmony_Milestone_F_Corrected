from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
sys.path.insert(0, str(CODE))

import csvplan_reconciled_alignment as a  # noqa: E402


class CsvplanReconciledAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.rules = {rule.key: rule for rule in a.RULES}

    def test_alignment_contract_is_internally_consistent(self):
        a.validate_contract(ROOT)
        p = a.provenance(ROOT)
        self.assertEqual(p["profile"], "milestone_f_csvplan_reconciled_alignment")
        self.assertFalse(p["numerical_solver_change_required"])
        self.assertEqual(p["alignment_scope"], "provenance_and_documentation")

    def test_reference_checkpoints_are_pinned(self):
        self.assertEqual(a.CSVPLAN_RECONCILED_COMMIT, "ded576c5b8c80d2bbc9fbf3a8a7a391f0a64a433")
        self.assertEqual(a.E_NUMERICAL_BASELINE_COMMIT, "3faf1657bf0df93906477ed3ba85766406f323ba")
        self.assertEqual(a.E_ALIGNMENT_GATE_COMMIT, "eecbc29ec6b82a677545eca4f9540d1623328d98")
        self.assertEqual(a.F_PRE_ALIGNMENT_COMMIT, "d71a68c6f02cde756ed814b8e209b23177ab56e0")

    def test_embedded_e_solver_is_exactly_the_aligned_e_numerical_blob(self):
        path = CODE / "new_harmony_empirical_e_corrected.py"
        self.assertEqual(a.git_blob_sha(path), a.EXPECTED_EMBEDDED_E_GIT_BLOB)

    def test_physical_core_is_recorded_as_aligned(self):
        for key in ("vector_accounting", "robust_harmony", "stock_recurrence", "cohort_depreciation"):
            self.assertTrue(self.rules[key].status.startswith("aligned"))
        self.assertEqual(self.rules["candidate_admissibility"].status, "structural_equivalent")

    def test_iterative_controller_rules_are_not_misattributed_to_final_f(self):
        for key in ("destination_priority", "source_year_selection", "c26_increment", "epsilon", "cv_stopping"):
            self.assertEqual(self.rules[key].status, "not_applicable")

    def test_f_has_no_warm_start_semantics(self):
        rule = self.rules["preliminary_schedule"]
        self.assertEqual(rule.status, "milestone_f_architecture_choice")
        self.assertIn("endogenous", rule.implementation)
        self.assertNotIn("warm start", rule.implementation.lower())
        self.assertNotIn("70%", rule.implementation)

    def test_lexicographic_hierarchy_is_explicitly_an_f_extension(self):
        self.assertEqual(self.rules["lexicographic_objective"].status, "milestone_f_extension")
        self.assertEqual(self.rules["harmony_approximation"].status, "milestone_f_numerical_extension")

    def test_capital_bundle_and_asset_filter_are_f_empirical_extensions(self):
        self.assertEqual(self.rules["capital_bundle"].status, "milestone_f_empirical_extension")
        self.assertEqual(self.rules["asset_source_restriction"].status, "milestone_f_empirical_extension")
        self.assertEqual(self.rules["historical_dynamic_C"].status, "milestone_f_ex_post_diagnostic")

    def test_shadow_horizon_is_f_boundary_not_csvplan_terminal_rule(self):
        rule = self.rules["terminal_boundary"]
        self.assertEqual(rule.status, "milestone_f_boundary_extension")
        self.assertIn("three stationary shadow years", rule.implementation)


if __name__ == "__main__":
    unittest.main(verbosity=2)
