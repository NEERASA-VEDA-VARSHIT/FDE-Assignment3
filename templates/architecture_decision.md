# Architecture Decision Memo

**Ship: single-agent baseline (Architecture A).**
Model: `nvidia/nemotron-3-super-120b-a12b:free`, same model/temperature/evidence for both runs.

## Evidence

Same 6 public cases on both architectures:

| Metric | Single agent | Staged / 2-agent |
|---|---:|---:|
| Cases passing minimum checks | 6/6 (100%) | 6/6 (100%) |
| Avg latency | 4511.5 ms | 10745.6 ms |
| Avg LLM calls | 1.0 | 2.0 |
| Avg tool calls | 4.0 | 4.0 |
| Notable policy/grounding failures | 0 | 0 |

Per-case (single | staged): PUB-01 3595ms | 13161ms; PUB-02 8028ms | 8227ms; PUB-03 4870ms | 16393ms; PUB-04 3038ms | 10737ms; PUB-05 1803ms | 6345ms; PUB-06 5731ms | 9608ms. Covers low-value approval, catalog overlap, source-code sensitivity, budget shortfall, incomplete+injection, API outage.

## Trade-offs

Staged adds a research-summary LLM call with no quality gain on the public set: +6.2s/case (+138%), 2x LLM cost and failure surface, same 4 deterministic tools. Deterministic approvals/risks/missing-info are enforced outside the LLM in both, with `human_review_required=True`, so the extra summarization did not change controls.

## Risks / limitations

Public set is only 6 cases; hidden conflicting/expired-vendor and novel injection cases still need validation. No prod load, cost-at-scale, or human UX review yet. Vendor-risk outage handling (treat unavailable as non-favorable + route to human) held for PUB-06 but needs continued monitoring.

## Why this is the right MVP

The client needs grounded evidence plus a safe next-action with humans retaining approvals. Single-agent meets all required outputs, is cheaper/faster/simpler to operate and debug, and leaves policy authority in code, not the model. Per brief guidance, the simpler system that performs as well is the stronger ship choice. (158 words)
