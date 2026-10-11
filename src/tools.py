from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _native(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, dict):
        return {k: _native(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_native(v) for v in value]
    return value

from src.data_access import (
    get_request,
    load_budgets,
    load_employees,
    load_software_catalog,
    load_vendors,
)
from src.policy_engine import PolicyEvaluation, evaluate_policy
from src.vendor_client import get_vendor_risk


@dataclass(frozen=True)
class ToolResult:
    name: str
    data: Any
    error: str | None = None


def get_requester_context(employee_id: str) -> dict:
    rows = load_employees()
    matches = rows[rows["employee_id"].astype(str) == str(employee_id)]
    if matches.empty:
        raise KeyError(f"Unknown employee_id: {employee_id}")
    return _native(matches.iloc[0].to_dict())


def get_employee_budget(employee_id: str) -> dict:
    employee = get_requester_context(employee_id)
    budgets = load_budgets()
    matches = budgets[budgets["department"] == employee["department"]]
    if matches.empty:
        raise KeyError(f"No budget record for department: {employee['department']}")
    return _native(matches.iloc[0].to_dict())


def search_software_catalog(
    product_name: str,
    vendor_name: str,
    category: str,
) -> list[dict]:
    catalog = load_software_catalog().fillna("")
    fields = [product_name, vendor_name, category]
    mask = False
    for value in fields:
        text = str(value or "").strip().lower()
        if not text:
            continue
        mask = mask | catalog.apply(
            lambda row: text in str(row["product_name"]).lower()
            or text in str(row["vendor_name"]).lower()
            or text in str(row["category"]).lower()
            or text in str(row["notes"]).lower(),
            axis=1,
        )
    return _native(catalog[mask].to_dict(orient="records"))


def get_vendor_security_status(vendor_name: str) -> ToolResult:
    registry = load_vendors()
    matches = registry[registry["vendor_name"] == vendor_name]
    if matches.empty:
        raise KeyError(f"Unknown vendor: {vendor_name}")
    registry_record = _native(matches.iloc[0].to_dict())
    try:
        api_record = get_vendor_risk(vendor_name)
        return ToolResult(
            name="get_vendor_security_status",
            data={"registry": registry_record, "risk_service": api_record},
        )
    except Exception as exc:
        return ToolResult(
            name="get_vendor_security_status",
            data={"registry": registry_record, "risk_service": None},
            error=f"{type(exc).__name__}: {exc}",
        )


def check_procurement_policy(
    request: dict,
    employee: dict,
    budget: dict,
    vendor_registry: dict,
    vendor_risk: dict | None,
    vendor_risk_available: bool,
    existing_software: list[dict],
) -> PolicyEvaluation:
    return evaluate_policy(
        request,
        employee=employee,
        budget=budget,
        vendor_registry=vendor_registry,
        vendor_risk=vendor_risk,
        vendor_risk_available=vendor_risk_available,
        existing_software=existing_software,
    )


def gather_evidence(request_id: str) -> tuple[dict, dict]:
    """Deterministic evidence gathering used by both architectures."""
    request = get_request(request_id)
    employee = get_requester_context(request["requester_id"])
    budget = get_employee_budget(request["requester_id"])
    catalog_matches = search_software_catalog(
        request["product_name"], request["vendor_name"], request["category"]
    )
    vendor_result = get_vendor_security_status(request["vendor_name"])

    vendor_registry = vendor_result.data["registry"]
    vendor_risk = vendor_result.data["risk_service"]
    policy = check_procurement_policy(
        request,
        employee,
        budget,
        vendor_registry,
        vendor_risk,
        vendor_result.error is None,
        catalog_matches,
    )

    evidence = {
        "request": request,
        "employee": employee,
        "budget": budget,
        "catalog_matches": catalog_matches,
        "vendor_registry": vendor_registry,
        "vendor_risk": vendor_risk,
        "vendor_risk_error": vendor_result.error,
        "policy": {
            "required_approvals": policy.required_approvals,
            "missing_information": policy.missing_information,
            "risk_flags": policy.risk_flags,
            "reasons": policy.reasons,
        },
    }
    telemetry = {
        "tool_names": [
            "get_employee_budget",
            "search_software_catalog",
            "get_vendor_security_status",
            "check_procurement_policy",
        ],
        "tool_calls": 4,
    }
    return evidence, telemetry
