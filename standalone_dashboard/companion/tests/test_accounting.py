from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from eco_companion.accounting import compute_accounts
from eco_companion.physical_accounting import compute_physical_accounts


class AccountingTests(unittest.TestCase):
    def test_qualitative_values_remain_categories_and_source_rows_are_not_mutated(self):
        rows = [
            {"technology_mode": "frozen", "year": 2019, "published": 1, "bea_code": "A", "sector_name": "Alpha", "gross_output_real_musd": 10.0},
            {"technology_mode": "frozen", "year": 2020, "published": 1, "bea_code": "A", "sector_name": "Alpha", "gross_output_real_musd": 12.0},
        ]
        original = [dict(row) for row in rows]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "assoc.csv").write_text("ID,Settore,CO2\n1,Alpha,2\n", encoding="utf-8")
            (root / "cross.csv").write_text(
                "f_bea_code,f_sector_name,eco_id,eco_sector_name,allocation_share,mapping_status,note\nA,Alpha,1,Alpha,1,mapped,direct\n",
                encoding="utf-8",
            )
            summary, contributions, coverage = compute_accounts(rows, root / "assoc.csv", root / "cross.csv")
        self.assertEqual(rows, original)
        self.assertEqual(summary[0]["characteristic_sector_count"], 1)
        self.assertEqual(summary[1]["characteristic_sector_count"], 1)
        self.assertEqual(len(contributions), 2)
        self.assertEqual(contributions[0]["association_level"], 2)
        self.assertEqual(contributions[1]["association_label"], "caratteristica")
        self.assertEqual(contributions[0]["published"], 1)
        self.assertEqual(coverage[0]["coverage_ratio"], 1.0)

    def test_physical_mass_uses_2012_base_and_2019_activity_ratio(self):
        rows = [
            {"technology_mode": "frozen", "year": 2019, "published": 1, "bea_code": "A", "sector_name": "Alpha", "gross_output_real_musd": 60.0, "observed_gross_output_2019_real_musd": 50.0},
            {"technology_mode": "frozen", "year": 2020, "published": 1, "bea_code": "A", "sector_name": "Alpha", "gross_output_real_musd": 75.0, "observed_gross_output_2019_real_musd": 50.0},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "coeff.csv").write_text("ID,Settore,CO2\n1,Alpha,2\n", encoding="utf-8")
            (root / "base.csv").write_text("ID,Settore,output_2012_million_usd\n1,Alpha,100\n", encoding="utf-8")
            (root / "cross.csv").write_text(
                "f_bea_code,f_sector_name,eco_id,eco_sector_name,allocation_share,mapping_status,note\nA,Alpha,1,Alpha,1,mapped,direct\n",
                encoding="utf-8",
            )
            summary, contributions = compute_physical_accounts(rows, root / "coeff.csv", root / "base.csv", root / "cross.csv")
        self.assertAlmostEqual(contributions[0]["value_kg"], 240.0)
        self.assertAlmostEqual(contributions[1]["value_kg"], 300.0)
        self.assertEqual(summary[0]["index_2019_100"], 100.0)
        self.assertEqual(summary[1]["index_2019_100"], 125.0)
        self.assertEqual(contributions[1]["signal"], "n.d.")


if __name__ == "__main__":
    unittest.main()
