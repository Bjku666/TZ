from __future__ import annotations

from unittest import TestCase

from backend.services.rules_service import rules_config


class RulesConfigApiTests(TestCase):
    def test_rules_config_exposes_canonical_thresholds(self) -> None:
        data = rules_config()
        config = data["config"]

        self.assertEqual(config["lotSize"], 100)
        self.assertEqual(config["turnoverTopN"], 30)
        self.assertEqual(config["buyZone"]["maxDeviationPct"], 2.5)
        self.assertEqual(config["singleTradeRisk"]["maxPct"], 0.02)
        self.assertEqual(config["buyWindows"][0], {"start": "09:35", "end": "10:00"})
        self.assertEqual(config["riskCheckTime"], "14:50")
