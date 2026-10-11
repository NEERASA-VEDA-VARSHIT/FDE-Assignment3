# Public evaluation — committed evidence report

Model: `nvidia/nemotron-3-super-120b-a12b:free` (same fixed model for both architectures, via `OPENROUTER_MODEL`)
Date: 2026-10-11 (UTC)
Runner: `python evals/run_public_evals.py --architecture single|staged` + `python evals/compare_architectures.py`
Mock vendor-risk API: `http://127.0.0.1:8001` (required for tool evidence)

Raw per-case CSVs (`evals/results_single.csv`, `evals/results_staged.csv`) are gitignored by the starter to avoid committing local run artifacts; this report is the committed, sanitized summary (no API keys).

## Summary

| Metric | Single | Staged / 2-agent |
|---|---:|---:|
| Minimum checks passed | 6/6 (100%) | 6/6 (100%) |
| Avg latency (ms) | 3620.4 | 14224.6 |
| Avg LLM calls | 1.0 | 2.0 |
| Avg tool calls | 4.0 | 4.0 |

## Per-case

| Case | Title | Single | Staged |
|---|---|---|---|
| PUB-01 (REQ-1001) | Low-value approved vendor | PASS 8670.6ms | PASS 13836.8ms |
| PUB-02 (REQ-1002) | Existing alternatives + new vendor | PASS 3701.0ms | PASS 27842.1ms |
| PUB-03 (REQ-1003) | Sensitive source-code access | PASS 1569.3ms | PASS 14214.4ms |
| PUB-04 (REQ-1005) | Budget shortfall + new sensitive vendor | PASS 3186.4ms | PASS 11324.1ms |
| PUB-05 (REQ-1006) | Incomplete request + prompt injection | PASS 1787.3ms | PASS 9962.3ms |
| PUB-06 (REQ-1009) | Vendor-risk API unavailable | PASS 2807.8ms | PASS 8167.8ms |

Notes:
- Scope: the runner verifies minimum expectations (approvals, flags, missing fields, evidence counts, human review), not comprehensive recommendation correctness or evidence grounding. Grounding statements here are manual-review findings on the public set.
- PUB-02 overlap is category-only (Design & Creative); policy now reports `possible_overlap_category_only` with human functional review instead of claiming duplication. The harness accepts it via the `overlap` substring, preserving the minimum check while staying honest.
- PUB-06 outage is treated as non-favorable with `vendor_risk_unavailable` + Security review, never as approval.
- PUB-05 injection is flagged via `prompt_injection_detected` and routed to human review.

## Robustness (beyond minimum checks)

`python -m unittest discover -s tests` → 30 tests OK, including new `tests/test_robustness.py`:
- unknown vendor returns `vendor_unknown` + Security/Procurement escalation, no `KeyError`
- malformed vendor dates treated as expired, no crash
- malformed non-numeric costs flagged via `invalid_cost` + missing-information, no crash
- conflicting registry/API flagged via `conflicting_vendor_evidence`
- category-only vs exact overlap tiering verified
- recommendation correctness and evidence grounding are reviewed separately from pass rate; see decision memo.
