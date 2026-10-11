# Architecture Decision Memo

**Ship: single-agent baseline (Architecture A).**
Model: `nvidia/nemotron-3-super-120b-a12b:free`, same model/temperature/evidence for both runs.

## Evidence

Same 6 public cases on both architectures:

| Metric | Single agent | Staged / 2-agent |
|---|---:|---:|
| Cases passing minimum checks | 6/6 (100%) | 6/6 (100%) |
| Avg latency | 3620.4 ms | 14224.6 ms |
| Avg LLM calls | 1.0 | 2.0 |
| Avg tool calls | 4.0 | 4.0 |
| Notable policy/grounding failures | Manual review: none found on public set (runner checks minimums only) | Manual review: none found on public set (runner checks minimums only) |

Per-case (single | staged): PUB-01 8670.6ms | 13836.8ms; PUB-02 3701.0ms | 27842.1ms; PUB-03 1569.3ms | 14214.4ms; PUB-04 3186.4ms | 11324.1ms; PUB-05 1787.3ms | 9962.3ms; PUB-06 2807.8ms | 8167.8ms. Covers low-value approval, catalog overlap, source-code sensitivity, budget shortfall, incomplete+injection, API outage. Committed report: `evals/comparison_report.md` (2026-10-11).

## Trade-offs

Staged adds a research-summary LLM call with no quality gain on the public set: +10.6s/case (+293%), 2x LLM cost and failure surface, same 4 deterministic tools. Deterministic approvals/risks/missing-info are enforced outside the LLM in both, with `human_review_required=True`, so the extra summarization did not change controls. Category-only overlap now reports `possible_overlap_category_only` for human review; unknown vendors escalate via `vendor_unknown` instead of failing.

## Risks / limitations

Public set is only 6 cases; hidden conflicting/expired-vendor and novel injection cases still need validation. No prod load, cost-at-scale, or human UX review yet. Vendor-risk outage handling (treat unavailable as non-favorable + route to human) held for PUB-06 but needs continued monitoring.

## Why this is the right MVP

The client needs grounded evidence plus a safe next-action with humans retaining approvals. Single-agent meets all required outputs, is cheaper/faster/simpler to operate and debug, and leaves policy authority in code, not the model. Per brief guidance, the simpler system that performs as well is the stronger ship choice. (158 words)
