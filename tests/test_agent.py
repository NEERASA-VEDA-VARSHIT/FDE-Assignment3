from __future__ import annotations

import unittest
import json
from unittest.mock import patch

from src.solution import handle_request


def fake_llm(messages):
    return {
        "recommendation": "Hold for human procurement review",
        "next_step": "Route the request and listed reviews to the appropriate human approvers.",
    }


def fake_research(messages):
    return {
        "summary": "Evidence gathered and deterministic policy findings preserved.",
        "material_uncertainties": [],
        "evidence_sources": ["employee_directory", "department_budgets", "software_catalog", "vendor_risk_service", "procurement_policy"],
    }


class AgentTests(unittest.TestCase):
    @patch("src.agent._request_json", side_effect=fake_llm)
    def test_single_uses_contract_and_four_tools(self, _mock):
        result = handle_request("REQ-1003", "single")
        self.assertEqual(result.request_id, "REQ-1003")
        self.assertIn("Security", result.required_approvals)
        self.assertIn("security_review_required", result.risk_flags)
        self.assertEqual(result.telemetry.llm_calls, 1)
        self.assertGreaterEqual(result.telemetry.tool_calls, 3)
        self.assertTrue(result.human_review_required)
        json.dumps(result.model_dump())

    @patch("src.agent._request_json", side_effect=fake_llm)
    def test_staged_uses_two_llm_calls(self, mock):
        # The staged research call is in agent.py and shares the same mock.
        result = handle_request("REQ-1005", "staged")
        self.assertEqual(result.request_id, "REQ-1005")
        self.assertIn("Finance", result.required_approvals)
        self.assertIn("Security", result.required_approvals)
        self.assertIn("Privacy", result.required_approvals)
        self.assertIn("Legal", result.required_approvals)
        self.assertEqual(result.telemetry.llm_calls, 2)
        self.assertGreaterEqual(result.telemetry.tool_calls, 3)
        self.assertEqual(mock.call_count, 2)

    @patch("src.agent._request_json", side_effect=fake_llm)
    def test_missing_request_does_not_fabricate_financial_threshold(self, _mock):
        result = handle_request("REQ-1006", "single")
        self.assertIn("annual cost or reasonable annual estimate", result.missing_information)
        self.assertIn("number of users/licenses", result.missing_information)
        self.assertIn("prompt_injection_detected", result.risk_flags)
        self.assertNotIn("budget_insufficient", result.risk_flags)


if __name__ == "__main__":
    unittest.main()
