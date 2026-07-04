from __future__ import annotations

from unittest import TestCase

from backend.services.rules_service import rules_config


class RulesConfigApiTests(TestCase):
    def test_rules_config_exposes_canonical_thresholds(self) -> None:
        data = rules_config()
        config = data["config"]

        self.assertEqual(config["lotSize"], 100)
        self.assertEqual(config["turnoverTopN"], 20)
        self.assertEqual(config["touchTolerancePct"], 0.5)
        self.assertEqual(config["morningBuyWindow"], {"start": "09:30", "end": "10:00", "endExclusive": True})
        self.assertEqual(config["afternoonBuyWindow"], {"start": "14:30", "end": "15:00", "endExclusive": True})
        self.assertEqual(config["quoteFreshnessSeconds"], 20)
        self.assertIn("executionConstraints", config)
