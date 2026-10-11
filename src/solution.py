from __future__ import annotations

from src.contracts import Architecture, ProcurementDecision
from src.agent import run_single, run_staged


def handle_request(request_id: str, architecture: Architecture = "single") -> ProcurementDecision:
    """Stable evaluation adapter for both assessment architectures."""
    if architecture == "single":
        return run_single(request_id)
    if architecture == "staged":
        return run_staged(request_id)
    raise ValueError(f"Unsupported architecture: {architecture}")
