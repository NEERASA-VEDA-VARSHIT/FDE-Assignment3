from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from src.solution import handle_request

ROOT = Path(__file__).resolve().parent
REQUESTS = json.loads((ROOT / "data" / "requests.json").read_text(encoding="utf-8"))
BY_ID = {r["request_id"]: r for r in REQUESTS}

st.set_page_config(page_title="Procurement Request Copilot", layout="wide")
st.title("AI Procurement Request Copilot")
st.caption("AI recommends; deterministic policy checks enforce controls; humans approve.")

request_id = st.sidebar.selectbox(
    "Request",
    list(BY_ID.keys()),
    format_func=lambda rid: f"{rid} — {BY_ID[rid]['product_name']}",
)
architecture = st.sidebar.radio(
    "Architecture",
    ["single", "staged"],
    format_func=lambda value: (
        "A · Single-agent baseline" if value == "single" else "B · Staged / 2-agent"
    ),
)
req = BY_ID[request_id]

left, right = st.columns([0.95, 1.05], gap="large")

with left:
    st.subheader("Request details")
    st.json(req)

with right:
    st.subheader("Copilot recommendation")
    if st.button("Run analysis", type="primary", use_container_width=True):
        try:
            result = handle_request(request_id, architecture=architecture)
        except Exception as exc:
            st.error(str(exc))
            st.info("Check VENDOR_RISK_BASE_URL, OPENROUTER_API_KEY, and OPENROUTER_MODEL in .env.")
        else:
            st.success(result.recommendation)

            action_col, review_col = st.columns(2)
            with action_col:
                st.markdown("**Next step**")
                st.write(result.next_step)
            with review_col:
                st.markdown("**Human review**")
                st.write("Required" if result.human_review_required else "Not required")

            st.markdown("**Required approvals**")
            if result.required_approvals:
                st.write(", ".join(result.required_approvals))
            else:
                st.write("None identified by the deterministic policy engine.")

            st.markdown("**Risk flags**")
            if result.risk_flags:
                for flag in result.risk_flags:
                    st.warning(flag)
            else:
                st.write("No policy risk flags.")

            st.markdown("**Missing information**")
            if result.missing_information:
                for item in result.missing_information:
                    st.warning(item)
            else:
                st.write("None.")

st.divider()

st.subheader("Evidence")
if "result" in locals():
    for item in result.evidence:
        with st.expander(f"{item.source}: {item.finding}", expanded=True):
            if item.reference:
                st.caption(f"Reference: {item.reference}")
else:
    st.info("Run an analysis to populate the evidence panel.")

st.caption(
    "Recommendations are advisory. The copilot cannot purchase software, approve spend, "
    "change budgets, or override Security, Privacy, or Legal."
)
