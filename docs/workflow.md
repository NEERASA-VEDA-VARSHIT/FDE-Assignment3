# Architecture and workflow

## Shared deterministic evidence layer

```text
Request
  |
  +--> get_employee_budget --------------------+
  +--> search_software_catalog -----------------+
  +--> get_vendor_security_status --------------+--> check_procurement_policy
                                                 |
                                                 v
                                      deterministic findings
                                      approvals / risks / missing info
                                                 |
                         +-----------------------+----------------------+
                         |                                              |
                  Architecture A                               Architecture B
                  1 decision agent                       1 research agent
                         |                                1 decision agent
                         +-----------------------+----------------------+
                                                 |
                                                 v
                                    ProcurementDecision
                                                 |
                                                 v
                                           Human review
```

## Tools

1. `get_employee_budget` — deterministic employee-to-department budget lookup.
2. `search_software_catalog` — deterministic catalog/overlap lookup.
3. `get_vendor_security_status` — registry + mock external vendor-risk API.
4. `check_procurement_policy` — deterministic policy engine.

The policy engine is authoritative for financial thresholds, budget shortfalls, security/privacy/legal review, stale/conflicting vendor evidence, missing information, and prompt-injection flags.

## Architecture A

One LLM decision call receives the same gathered evidence and deterministic policy findings. It generates only the recommendation and next step; deterministic fields are preserved outside the model.

## Architecture B

A first LLM call creates an evidence/research summary. A second LLM call turns that summary plus the original traceable evidence and policy findings into a recommendation and next step.

Both architectures use the same tools, policy engine, model, temperature, request set, and output contract. This makes the experiment primarily about orchestration rather than changing the underlying evidence.

## Human authority

Neither architecture can purchase software, approve spend, change budgets, accept legal terms, or override Security/Privacy/Legal.
