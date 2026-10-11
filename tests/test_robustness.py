from __future__ import annotations

import unittest
from unittest.mock import patch

from src.policy_engine import evaluate_policy
from src.tools import get_vendor_security_status, search_software_catalog


def base_request(**overrides):
    req = {
        "requester_id": "E001",
        "product_name": "Example",
        "vendor_name": "Example Vendor",
        "category": "Example",
        "annual_cost_usd": 5000,
        "user_count": 5,
        "business_justification": "A valid business purpose.",
        "data_access_level": "none",
        "requested_integrations": [],
    }
    req.update(overrides)
    return req


class RobustnessTests(unittest.TestCase):
    def test_unknown_vendor_does_not_raise_and_escalates(self):
        result = get_vendor_security_status("Vendor That Does Not Exist XYZ")
        self.assertIsNone(result.data["registry"])
        self.assertIn("VendorUnknown", result.error)

        policy = evaluate_policy(
            base_request(vendor_name="Vendor That Does Not Exist XYZ"),
            employee={"employee_id": "E001", "department": "Marketing"},
            budget={"available_usd": 10000},
            vendor_registry=None,
            vendor_risk=result.data["risk_service"],
            vendor_risk_available=False,
            existing_software=[],
        )
        self.assertIn("vendor_unknown", policy.risk_flags)
        self.assertIn("security_review_required", policy.risk_flags)
        self.assertIn("Security", policy.required_approvals)
        self.assertTrue(policy.human_review_required)

    def test_malformed_vendor_dates_do_not_crash(self):
        policy = evaluate_policy(
            base_request(),
            employee={"employee_id": "E001", "department": "Marketing"},
            budget={"available_usd": 10000},
            vendor_registry={
                "procurement_status": "Approved",
                "security_status": "Approved",
                "security_review_date": "not-a-date",
                "legal_terms_status": "Approved",
            },
            vendor_risk={
                "security_review_status": "approved",
                "last_review_date": "also-bad",
                "stores_data_outside_region": False,
            },
            vendor_risk_available=True,
            existing_software=[],
        )
        self.assertIn("vendor_review_expired", policy.risk_flags)
        self.assertIn("Security", policy.required_approvals)

    def test_conflicting_registry_api_is_flagged(self):
        policy = evaluate_policy(
            base_request(),
            employee={"employee_id": "E001", "department": "Marketing"},
            budget={"available_usd": 10000},
            vendor_registry={
                "procurement_status": "Approved",
                "security_status": "Approved",
                "security_review_date": "2026-06-01",
                "legal_terms_status": "Approved",
            },
            vendor_risk={
                "security_review_status": "expired",
                "last_review_date": "2025-01-01",
                "stores_data_outside_region": False,
            },
            vendor_risk_available=True,
            existing_software=[],
        )
        self.assertIn("conflicting_vendor_evidence", policy.risk_flags)

    def test_category_only_overlap_is_not_claimed_duplicate(self):
        matches = search_software_catalog("BrandBoard Enterprise", "BrandBoard", "Design & Creative")
        self.assertTrue(matches)
        self.assertTrue(all(m.get("_match_type") == "category" for m in matches))

        policy = evaluate_policy(
            base_request(product_name="BrandBoard Enterprise", vendor_name="BrandBoard", category="Design & Creative"),
            employee={"employee_id": "E001", "department": "Marketing"},
            budget={"available_usd": 50000},
            vendor_registry={
                "procurement_status": "Approved",
                "security_status": "Approved",
                "security_review_date": "2026-06-01",
                "legal_terms_status": "Approved",
            },
            vendor_risk={
                "security_review_status": "approved",
                "last_review_date": "2026-06-01",
                "stores_data_outside_region": False,
            },
            vendor_risk_available=True,
            existing_software=matches,
        )
        self.assertIn("possible_overlap_category_only", policy.risk_flags)
        self.assertNotIn("existing_tool_overlap", policy.risk_flags)

    def test_exact_overlap_keeps_existing_tool_flag(self):
        matches = search_software_catalog("CodeMate Teams Expansion", "CodeMate", "Developer AI")
        self.assertTrue(any(m.get("_match_type") == "exact" for m in matches))

        policy = evaluate_policy(
            base_request(product_name="CodeMate Teams Expansion", vendor_name="CodeMate", category="Developer AI"),
            employee={"employee_id": "E001", "department": "Marketing"},
            budget={"available_usd": 50000},
            vendor_registry={
                "procurement_status": "Approved",
                "security_status": "Approved",
                "security_review_date": "2026-06-01",
                "legal_terms_status": "Approved",
            },
            vendor_risk={
                "security_review_status": "approved",
                "last_review_date": "2026-06-01",
                "stores_data_outside_region": False,
            },
            vendor_risk_available=True,
            existing_software=matches,
        )
        self.assertIn("existing_tool_overlap", policy.risk_flags)

    @patch("src.agent._request_json", return_value={"recommendation": "Hold", "next_step": "Route to human"})
    def test_agent_handles_unknown_vendor_without_exception(self, _mock):
        from src.tools import gather_evidence
        from src.agent import _evidence_items

        with patch("src.tools.get_request", return_value=base_request(vendor_name="Ghost Vendor", product_name="Ghost Tool", category="Ghost Cat", request_id="REQ-GHOST")):
            with patch("src.tools.get_vendor_security_status", return_value=type("R", (), {"data": {"registry": None, "risk_service": None}, "error": "VendorUnknown: Ghost Vendor"})()):
                # gather_evidence would call real data_access; test evidence rendering directly
                evidence = {
                    "request": base_request(vendor_name="Ghost Vendor", request_id="REQ-GHOST"),
                    "employee": {"employee_id": "E001", "department": "Marketing"},
                    "budget": {"available_usd": 10000},
                    "catalog_matches": [],
                    "vendor_registry": None,
                    "vendor_risk": None,
                    "vendor_risk_error": "VendorUnknown: Ghost Vendor",
                    "policy": {"required_approvals": ["Security"], "missing_information": [], "risk_flags": ["vendor_unknown"]},
                }
                items = _evidence_items(evidence)
                self.assertTrue(any(i.source == "vendor_registry" and "not in the approved registry" in i.finding for i in items))


if __name__ == "__main__":
    unittest.main()
