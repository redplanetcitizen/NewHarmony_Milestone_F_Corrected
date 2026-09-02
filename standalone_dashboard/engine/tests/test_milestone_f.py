from __future__ import annotations

from pathlib import Path
import csv
import json
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
CODE = ROOT / "code"
sys.path.insert(0, str(CODE))

import new_harmony_empirical_f as f  # noqa: E402


def rows(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


class TestMilestoneFCorrected(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.variants = rows(RES / "VARIANT_COMPARISON.csv")
        cls.annual = rows(RES / "VARIANT_ANNUAL.csv")
        cls.outputs = rows(RES / "OUTPUT_AGGREGATE_COMPARISON.csv")

    def get(self, variant: str, mode: str) -> dict[str, str]:
        return next(
            row for row in self.variants
            if row["variant"] == variant and row["technology_mode"] == mode
        )

    def output(self, variant: str, mode: str) -> dict[str, str]:
        return next(
            row for row in self.outputs
            if row["variant"] == variant and row["technology_mode"] == mode
        )

    def test_01_corrected_e_is_the_current_baseline(self):
        expected = {
            "frozen": (0.4196346594277191, 0.2687727901475962),
            "historical": (0.4194880521717638, 0.2747260691466431),
        }
        for mode, (mean, investment_ratio) in expected.items():
            row = self.get("E_corrected_baseline", mode)
            self.assertAlmostEqual(float(row["mean_harmony_2019_2023"]), mean, places=11)
            self.assertAlmostEqual(float(row["investment_over_bea_2019_2023"]), investment_ratio, places=11)

    def test_02_legacy_eplus1_is_explicitly_separated(self):
        for mode in ("frozen", "historical"):
            self.get("E+1_legacy_maxmin_diagnostic", mode)
        self.assertFalse(any(r["variant"] == "E_baseline" for r in self.variants))

    def test_03_final_f_thresholds(self):
        self.assertGreaterEqual(
            float(self.get("F_corrected_5plus3_shadow", "frozen")["min_fulfillment_2019_2023"]),
            0.89,
        )
        self.assertGreaterEqual(
            float(self.get("F_corrected_5plus3_shadow", "historical")["min_fulfillment_2019_2023"]),
            0.95,
        )

    def test_04_final_stock_and_investment_are_economically_bounded(self):
        for mode in ("frozen", "historical"):
            row = self.get("F_corrected_5plus3_shadow", mode)
            self.assertGreaterEqual(float(row["stock_end_2023_over_bea"]), 0.90)
            ratio = float(row["investment_over_bea_2019_2023"])
            self.assertGreater(ratio, 0.0)
            self.assertLess(ratio, 1.0)

    def test_05_three_shadow_years_and_zero_final_investment(self):
        for mode in ("frozen", "historical"):
            selected = [
                row for row in self.annual
                if row["variant"] == "F_corrected_5plus3_shadow"
                and row["technology_mode"] == mode
            ]
            self.assertEqual(len(selected), 8)
            self.assertEqual(sum(int(row["published"]) for row in selected), 5)
            self.assertEqual([int(row["year"]) for row in selected[-3:]], [2024, 2025, 2026])
            self.assertAlmostEqual(float(selected[-1]["investment_real_musd"]), 0.0, places=8)

    def test_06_every_final_year_passes_the_corrected_constraint_audit(self):
        for mode in ("frozen", "historical"):
            audit = rows(RES / "F_final" / mode / "constraint_audit.csv")
            self.assertEqual(len(audit), 8)
            self.assertTrue(all(row["compliant"] == "True" for row in audit))
            self.assertTrue(all(row["flow_balance_ok"] == "True" for row in audit))
            self.assertTrue(all(row["stock_recurrence_ok"] == "True" for row in audit))
            self.assertTrue(all(row["capital_ok"] == "True" for row in audit))
            self.assertTrue(all(row["labour_ok"] == "True" for row in audit))
            self.assertTrue(all(row["imports_ok"] == "True" for row in audit))
            self.assertTrue(all(row["net_output_ok"] == "True" for row in audit))
            self.assertTrue(all(row["investment_ok"] == "True" for row in audit))

    def test_07_all_lp_variants_export_compliant_audits(self):
        for variant in ("E+2_forward_cell", "E+3_dynamic_bundle", "F_corrected_5plus3_shadow"):
            for mode in ("frozen", "historical"):
                audit = rows(RES / variant / mode / "constraint_audit.csv")
                self.assertTrue(audit)
                self.assertTrue(all(row["compliant"] == "True" for row in audit))

    def test_08_fulfillment_respects_all_reported_resource_bounds(self):
        for mode in ("frozen", "historical"):
            annual = rows(RES / "F_final" / mode / "annual_path.csv")
            for row in annual:
                fulfillment = float(row["fulfillment"])
                self.assertLessEqual(fulfillment, float(row["capital_constraint"]) + 1e-5)
                self.assertLessEqual(fulfillment, float(row["labour_constraint"]) + 1e-5)
                self.assertLessEqual(fulfillment, float(row["import_constraint"]) + 1e-5)
                self.assertGreaterEqual(fulfillment, -1e-10)
                self.assertLessEqual(fulfillment, 1.0 + 1e-10)

    def test_09_f_improves_worst_year_over_corrected_e(self):
        for mode in ("frozen", "historical"):
            e_min = float(self.get("E_corrected_baseline", mode)["min_fulfillment_2019_2023"])
            f_min = float(self.get("F_corrected_5plus3_shadow", mode)["min_fulfillment_2019_2023"])
            self.assertGreater(f_min, e_min)

    def test_10_gross_output_improves_over_corrected_e(self):
        for mode in ("frozen", "historical"):
            e_ratio = float(self.output("E_corrected_baseline", mode)["gross_model_over_bea"])
            f_ratio = float(self.output("F_corrected_5plus3_shadow", mode)["gross_model_over_bea"])
            self.assertGreater(f_ratio, e_ratio)

    def test_11_terminal_treatments_are_not_double_counted(self):
        for mode in ("frozen", "historical"):
            metadata = json.loads((RES / "F_final" / mode / "RUN_METADATA.json").read_text(encoding="utf-8"))
            self.assertFalse(metadata["terminal_equation_from_e_corrected_applied"])
            self.assertIn("three_stationary_shadow_years", metadata["terminal_treatment"])
            self.assertTrue(metadata["all_constraint_reports_compliant"])

    def test_12_no_seventy_percent_floor_is_present(self):
        source = (CODE / "new_harmony_empirical_f.py").read_text(encoding="utf-8")
        self.assertNotIn("0.7 *", source)
        self.assertNotIn("70-percent replacement", source)

    def test_13_corrected_reference_and_legacy_reference_are_preserved(self):
        self.assertTrue((ROOT / "reference" / "NewHarmony_Milestone_E_Corrected.zip").exists())
        self.assertTrue((ROOT / "reference" / "NewHarmony_Milestone_E.zip").exists())

    def test_14_harmony_function_is_unchanged(self):
        self.assertAlmostEqual(float(f.c.harmony(1.0)), 1.0 / 2.1, places=14)


if __name__ == "__main__":
    unittest.main(verbosity=2)
