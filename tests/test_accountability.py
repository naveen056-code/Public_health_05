import json
import unittest

from clinic_broker import accountability


class TestAccountabilityModule(unittest.TestCase):
    def test_required_changes_extraction(self):
        report = """VERDICT: REVISE
Summary of issues:
1. Stop 2 is too close to Stop 1.

REQUIRED CHANGES
- Re-run with min_spacing_km=6.0.
- Ensure stop 3 has referral clinic.
"""
        extracted = accountability._required_changes(report)
        self.assertIn("Re-run with min_spacing_km=6.0.", extracted)
        self.assertIn("Ensure stop 3 has referral clinic.", extracted)

        # Empty or no REQUIRED CHANGES section
        self.assertEqual(accountability._required_changes("Everything looks great."), "None.")

    def test_rows_from_mcp_structured(self):
        payload = {
            "structuredContent": {
                "schema": {"fields": [{"name": "col1"}, {"name": "col2"}]},
                "rows": [{"f": [{"v": "a"}, {"v": "1"}]}, {"f": [{"v": "b"}, {"v": "2"}]}],
            }
        }
        rows = accountability._rows_from_mcp(payload)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], {"col1": "a", "col2": "1"})
        self.assertEqual(rows[1], {"col1": "b", "col2": "2"})

    def test_rows_from_mcp_text_json(self):
        inner = {
            "schema": {"fields": [{"name": "val"}]},
            "rows": [{"f": [{"v": "100"}]}],
        }
        payload = {"content": [{"type": "text", "text": json.dumps(inner)}]}
        rows = accountability._rows_from_mcp(payload)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], {"val": "100"})

    def test_rows_from_mcp_invalid(self):
        self.assertIsNone(accountability._rows_from_mcp(None))
        self.assertIsNone(accountability._rows_from_mcp({}))
        self.assertIsNone(accountability._rows_from_mcp("not a dict"))

    def test_facts_empty_state(self):
        facts = accountability._facts({})
        self.assertEqual(facts["stops"], [])
        self.assertEqual(facts["people_living_in_stop_tracts"], 0)
        self.assertIsNone(facts["share_of_county_population_pct"])

    def test_facts_populated_state(self):
        state = {
            "plan_stops": [
                {
                    "saturday": "2026-11-07",
                    "geo_id": "13121000100",
                    "population": 5000,
                    "need_rank": 1,
                    "need_rank_note": "of 100 tracts",
                    "pct_uninsured": {"value": 25.0},
                    "pct_no_vehicle": {"value": 15.0},
                    "km_to_safety_net": {"value": 5.5},
                    "refer_to": {"display_name": "Clinic A"},
                }
            ],
            "evidence_need": {
                "county_totals": {"population": 100000, "median_km_to_safety_net": 3.0},
                "definition": "formula",
            },
            "audit_table": [
                {"grp": "plan", "population": "5000", "tracts": 1},
                {"grp": "need_pool", "population": "25000", "tracts": 5},
                {"grp": "county", "population": "100000", "tracts": 20},
            ],
        }
        facts = accountability._facts(state)
        self.assertEqual(facts["people_living_in_stop_tracts"], 5000)
        self.assertEqual(facts["share_of_county_population_pct"], 5.0)
        self.assertEqual(facts["stop_tracts_share_of_need_pool_population_pct"], 20.0)
        self.assertEqual(facts["median_km_to_safety_net_stops"], 5.5)


if __name__ == "__main__":
    unittest.main()
