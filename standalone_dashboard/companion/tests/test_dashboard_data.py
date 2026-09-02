from __future__ import annotations

import unittest

from eco_companion.dashboard_data import build_dashboard


class DashboardDataTests(unittest.TestCase):
    def test_sector_catalogue_and_full_contributions_are_exported(self):
        annual = [
            {"technology_mode": "frozen", "year": 2019, "published": 1},
            {"technology_mode": "frozen", "year": 2020, "published": 1},
        ]
        qualitative = [
            {"technology_mode": "frozen", "year": 2019, "pollutant": "CO2"},
            {"technology_mode": "frozen", "year": 2020, "pollutant": "CO2"},
        ]
        associations = [
            {"technology_mode": "frozen", "year": 2019, "pollutant": "CO2", "bea_code": "A", "sector_name": "Alpha", "association_level": 2},
            {"technology_mode": "frozen", "year": 2020, "pollutant": "CO2", "bea_code": "A", "sector_name": "Alpha", "association_level": 2},
        ]
        physical = [{"technology_mode": "frozen", "year": 2019, "pollutant": "CO2", "value_kg": 10}]
        physical_contributions = [{"technology_mode": "frozen", "year": 2019, "pollutant": "CO2", "bea_code": "A", "sector_name": "Alpha", "value_kg": 10}]
        coverage = [
            {"technology_mode": "frozen", "year": 2019, "coverage_ratio": 0.5},
            {"technology_mode": "frozen", "year": 2020, "coverage_ratio": 0.5},
        ]
        sectors = [
            {"technology_mode": "frozen", "year": 2019, "sector_index": 0, "bea_code": "A", "sector_name": "Alpha"},
            {"technology_mode": "frozen", "year": 2020, "sector_index": 0, "bea_code": "A", "sector_name": "Alpha"},
            {"technology_mode": "frozen", "year": 2019, "sector_index": 1, "bea_code": "B", "sector_name": "Beta"},
            {"technology_mode": "frozen", "year": 2020, "sector_index": 1, "bea_code": "B", "sector_name": "Beta"},
        ]
        source = {"repository": "example", "commit": "abc", "tree_sha256": "def"}

        dashboard = build_dashboard(annual, qualitative, associations, coverage, source, sector_rows=sectors, physical_rows=physical, physical_contribution_rows=physical_contributions)

        self.assertEqual([row["sector_name"] for row in dashboard["sectors"]], ["Alpha", "Beta"])
        self.assertTrue(dashboard["sectors"][0]["ecologically_mapped"])
        self.assertFalse(dashboard["sectors"][1]["ecologically_mapped"])
        self.assertEqual(len(dashboard["modes"]["frozen"]["sector_economy"]), 4)
        self.assertEqual(len(dashboard["modes"]["frozen"]["qualitative_associations"]), 2)
        self.assertEqual(len(dashboard["modes"]["frozen"]["physical_top_sectors"]["2019|CO2"]), 1)


if __name__ == "__main__":
    unittest.main()
