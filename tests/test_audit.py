import unittest

from clinic_broker import audit


class TestAuditModule(unittest.TestCase):
    def test_ids_sql_sanitization(self):
        # 11-digit FIPS codes should be retained
        valid_ids = ["13121000100", "13121000200"]
        sql_part = audit._ids_sql(valid_ids)
        self.assertEqual(sql_part, "'13121000100', '13121000200'")

        # SQL injection attempts or invalid lengths should be filtered out
        malicious_ids = ["13121000100", "13121000200' OR 1=1 --", "123", ""]
        sql_part_clean = audit._ids_sql(malicious_ids)
        self.assertEqual(sql_part_clean, "'13121000100'")

        # Empty list yields empty single quotes
        self.assertEqual(audit._ids_sql([]), "''")

    def test_audit_sql_generation(self):
        plan_ids = ["13121000100", "13121000200"]
        pool_ids = ["13121000100", "13121000200", "13121000300"]
        sql = audit.audit_sql(plan_ids, pool_ids)

        # Must include SAFE_DIVIDE to prevent BigQuery division by zero errors
        self.assertIn("SAFE_DIVIDE", sql)
        self.assertIn("'plan'", sql)
        self.assertIn("'need_pool'", sql)
        self.assertIn("'county'", sql)


if __name__ == "__main__":
    unittest.main()
