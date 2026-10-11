from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping


REFERENCE_DATE = date(2026, 9, 30)
VENDOR_REVIEW_VALIDITY_DAYS = 365


@dataclass(frozen=True)
class PolicyEvaluation:
    """Deterministic procurement-policy findings.

    This module intentionally contains no LLM calls and no request-ID-specific
    logic. It consumes evidence gathered by the surrounding application.
    """

    required_approvals: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    human_review_required: bool = True
    reasons: list[str] = field(default_factory=list)


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _contains_any(value: Any, needles: tuple[str, ...]) -> bool:
    text = _norm(value)
    return any(needle in text for needle in needles)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _parse_date(value: Any) -> date | None:
    if value in (None, "", "nan"):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except (ValueError, TypeError, AttributeError):
        return None


def _review_is_expired(review_date: Any) -> bool:
    parsed = _parse_date(review_date)
    if parsed is None:
        return True
    return (REFERENCE_DATE - parsed).days > VENDOR_REVIEW_VALIDITY_DAYS


def _prompt_injection_detected(request: Mapping[str, Any]) -> bool:
    text = " ".join(
        str(request.get(field, "") or "")
        for field in ("business_justification", "product_name", "category")
    ).lower()
    patterns = (
        "ignore all procurement rules",
        "ignore procurement rules",
        "ignore all rules",
        "bypass controls",
        "bypass procurement",
        "cfo-approved",
        "approve it immediately",
        "approve immediately",
        "ignore previous instructions",
    )
    return any(pattern in text for pattern in patterns)


def _security_use_case_requires_review(request: Mapping[str, Any]) -> bool:
    data_level = _norm(request.get("data_access_level"))
    integrations = request.get("requested_integrations") or []

    sensitive_levels = (
        "source_code",
        "production_telemetry",
        "confidential_documents",
        "employee_pii",
        "customer_pii",
        "credentials",
        "secrets",
    )
    if data_level in sensitive_levels:
        return True

    return any(
        _contains_any(
            integration,
            (
                "production",
                "cloud account",
                "cloud-account",
                "credential",
                "secret",
                "git repository",
                "git repositories",
                "source code",
            ),
        )
        for integration in integrations
    )


def _privacy_requires_review(
    request: Mapping[str, Any], vendor_risk: Mapping[str, Any] | None
) -> bool:
    data_level = _norm(request.get("data_access_level"))
    if data_level in {"employee_pii", "customer_pii"}:
        return True
    return bool(vendor_risk and vendor_risk.get("stores_data_outside_region"))


def _parse_cost(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        return float(str(value).strip().replace(",", ""))
    except (ValueError, TypeError, AttributeError):
        return None


def _legal_requires_review(
    request: Mapping[str, Any],
    vendor_registry: Mapping[str, Any] | None,
    vendor_risk: Mapping[str, Any] | None,
) -> bool:
    cost = request.get("annual_cost_usd")
    is_new_vendor = _norm((vendor_registry or {}).get("procurement_status")) == "new"
    parsed_cost = _parse_cost(cost)
    if is_new_vendor and parsed_cost is not None and parsed_cost >= 10_000:
        return True

    if _norm((vendor_registry or {}).get("legal_terms_status")) not in {"approved", "standard"}:
        return True

    # Policy §7 explicitly permits legal review for a material data-processing
    # or cross-region issue. Treat cross-region storage as material evidence.
    if vendor_risk and vendor_risk.get("stores_data_outside_region"):
        return True

    return False


def _threshold_approvals(cost: float) -> list[str]:
    if cost <= 1_000:
        return ["Manager"]
    if cost <= 10_000:
        return ["Department Head", "Procurement"]
    if cost <= 25_000:
        return ["Department Head", "Finance", "Procurement"]
    return ["Department Head", "Finance", "CFO", "Procurement"]


def evaluate_policy(
    request: Mapping[str, Any],
    *,
    employee: Mapping[str, Any],
    budget: Mapping[str, Any],
    vendor_registry: Mapping[str, Any] | None,
    vendor_risk: Mapping[str, Any] | None,
    vendor_risk_available: bool = True,
    existing_software: list[Mapping[str, Any]] | None = None,
) -> PolicyEvaluation:
    """Apply procurement policy deterministically to gathered evidence.

    The function does not decide whether a purchase is ultimately approved.
    It produces policy findings and the minimum human reviews required.
    """

    approvals: list[str] = []
    missing: list[str] = []
    flags: list[str] = []
    reasons: list[str] = []

    # §9 — requester text is untrusted business data.
    if _prompt_injection_detected(request):
        flags.append("prompt_injection_detected")
        reasons.append("Request text attempted to override procurement controls; embedded instructions are ignored.")

    # §1 — required request information.
    if not request.get("requester_id") or not employee:
        missing.append("requester and department")
    if not request.get("product_name") or not request.get("vendor_name"):
        missing.append("product/vendor")
    if request.get("annual_cost_usd") is None:
        missing.append("annual cost or reasonable annual estimate")
    if request.get("user_count") is None:
        missing.append("number of users/licenses")
    if not _norm(request.get("business_justification")):
        missing.append("business purpose")
    if not request.get("data_access_level") or _norm(request.get("data_access_level")) == "unknown":
        missing.append("intended data-access level")
    if "requested_integrations" not in request or request.get("requested_integrations") is None:
        missing.append("required integrations")

    if missing:
        flags.append("missing_information")
        reasons.append("Material request information is missing; values must not be invented.")

    cost = request.get("annual_cost_usd")
    if cost is not None:
        parsed = _parse_cost(cost)
        if parsed is None:
            missing.append("annual cost or reasonable annual estimate (invalid format)")
            flags.append("missing_information")
            flags.append("invalid_cost")
            reasons.append("Annual cost was supplied in an unparseable format; values must not be invented.")
        else:
            cost = parsed

            # §2 — budget.
            try:
                available = float(str(budget.get("available_usd", 0)).replace(",", ""))
            except (ValueError, TypeError, AttributeError):
                available = 0.0
            if cost > available:
                flags.append("budget_insufficient")
                approvals.append("Finance")
                reasons.append(
                    f"Annual cost ${cost:,.2f} exceeds available department budget ${available:,.2f}."
                )

            # §4 — deterministic financial threshold.
            approvals.extend(_threshold_approvals(cost))

    # §3 — overlap is surfaced with tiering, never automatic rejection.
    # Exact product/vendor matches suggest likely duplication; category-only
    # matches are possible alternatives needing human functional review.
    exact_matches = [m for m in (existing_software or []) if m.get("_match_type") == "exact"]
    category_matches = [m for m in (existing_software or []) if m.get("_match_type") == "category"]
    if exact_matches:
        flags.append("existing_tool_overlap")
        reasons.append("Existing catalog software matches the requested product/vendor and may duplicate the need.")
    elif category_matches:
        flags.append("possible_overlap_category_only")
        reasons.append("Category-only catalog matches exist; functional equivalence is unproven and needs human review.")
    elif existing_software:
        flags.append("existing_tool_overlap")
        reasons.append("Existing catalog software may overlap with the requested use case.")

    # Unknown vendor registry — never treat as safe; escalate.
    if vendor_registry is None:
        flags.append("vendor_unknown")
        flags.append("security_review_required")
        approvals.append("Security")
        approvals.append("Procurement")
        reasons.append("Vendor is not in the approved registry; registry controls cannot be verified.")

    # §5 — security review.
    registry_status = _norm((vendor_registry or {}).get("security_status"))
    registry_review_date = (vendor_registry or {}).get("security_review_date")
    api_status = _norm((vendor_risk or {}).get("security_review_status"))
    api_review_date = (vendor_risk or {}).get("last_review_date")

    registry_expired = (
        registry_status in {"expired", "not_completed", "pending", "unknown"}
        or _review_is_expired(registry_review_date)
    )
    api_expired = (
        api_status in {"expired", "not_completed", "pending", "unknown"}
        or _review_is_expired(api_review_date)
    )

    if not vendor_risk_available:
        flags.append("vendor_risk_unavailable")
        flags.append("security_review_required")
        approvals.append("Security")
        reasons.append("Current vendor-risk evidence could not be verified.")
    else:
        conflict = (
            registry_status
            and api_status
            and registry_status != api_status
        ) or (
            registry_review_date
            and api_review_date
            and str(registry_review_date) != str(api_review_date)
        )
        if conflict:
            flags.append("conflicting_vendor_evidence")
            flags.append("security_review_required")
            approvals.append("Security")
            reasons.append("Vendor registry and risk-service security evidence disagree.")

        if registry_expired or api_expired:
            flags.append("vendor_review_expired")
            flags.append("security_review_required")
            approvals.append("Security")
            reasons.append("Vendor security assessment is missing, incomplete, or older than 365 days.")

        if _security_use_case_requires_review(request):
            flags.append("security_review_required")
            approvals.append("Security")
            reasons.append("Requested data access or integration requires Security review.")

    # §6 — privacy.
    if _privacy_requires_review(request, vendor_risk):
        flags.append("privacy_review_required")
        approvals.append("Privacy")
        reasons.append("Requested data or storage location requires Privacy review.")

    # §7 — legal.
    if _legal_requires_review(request, vendor_registry, vendor_risk):
        flags.append("legal_review_required")
        approvals.append("Legal")
        reasons.append("Vendor terms, onboarding status, or cross-region/data-processing evidence requires Legal review.")

    return PolicyEvaluation(
        required_approvals=_unique(approvals),
        missing_information=_unique(missing),
        risk_flags=_unique(flags),
        human_review_required=True,
        reasons=_unique(reasons),
    )
