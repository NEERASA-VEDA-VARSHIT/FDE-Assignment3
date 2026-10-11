from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(architecture: str) -> list[dict]:
    path = ROOT / "evals" / f"results_{architecture}.csv"
    if not path.exists():
        raise SystemExit(f"Missing {path.name}. Run public evaluations for {architecture} first.")
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    single = load("single")
    staged = load("staged")
    if len(single) != len(staged):
        raise SystemExit("Architecture result files contain different numbers of cases.")

    def pct(rows: list[dict]) -> float:
        return 100 * sum(r["passed_minimum_checks"] == "True" for r in rows) / len(rows)

    def avg(rows: list[dict], field: str) -> float:
        values = [float(r[field]) for r in rows if r[field] != ""]
        return sum(values) / len(values) if values else 0.0

    print("Architecture comparison")
    print("=======================")
    print(f"Single:  {pct(single):.1f}% minimum-check pass | "
          f"{avg(single, 'latency_ms'):.1f} ms avg latency | "
          f"{avg(single, 'llm_calls'):.1f} avg LLM calls | "
          f"{avg(single, 'tool_calls'):.1f} avg tool calls")
    print(f"Staged:  {pct(staged):.1f}% minimum-check pass | "
          f"{avg(staged, 'latency_ms'):.1f} ms avg latency | "
          f"{avg(staged, 'llm_calls'):.1f} avg LLM calls | "
          f"{avg(staged, 'tool_calls'):.1f} avg tool calls")

    print("\nPer-case:")
    for a, b in zip(single, staged):
        print(
            f"{a['case_id']}: "
            f"single={'PASS' if a['passed_minimum_checks']=='True' else 'FAIL'} "
            f"{a['latency_ms']}ms | "
            f"staged={'PASS' if b['passed_minimum_checks']=='True' else 'FAIL'} "
            f"{b['latency_ms']}ms"
        )


if __name__ == "__main__":
    main()
