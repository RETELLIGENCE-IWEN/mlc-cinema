"""Lightweight sanity checks for parsed MLC content.

This is intentionally minimal in M0 — full schema validation is out of
scope. The checks here only flag conditions that would make replay
nonsensical (no states, states referencing undeclared bodies, etc.).
"""

from __future__ import annotations

import logging

from mlc_cinema.mlc.records import MLCParseResult

_log = logging.getLogger(__name__)


def warn_on_suspicious_content(result: MLCParseResult) -> list[str]:
    """Return human-readable warnings for suspicious-but-non-fatal conditions."""

    warnings: list[str] = []

    if result.header is None:
        warnings.append("No header record found.")

    if not result.bodies:
        warnings.append("No body records found.")

    if not result.states:
        warnings.append("No state records found.")

    referenced_unknown = sorted(
        {s.body_id for s in result.states if s.body_id not in result.bodies}
    )
    if referenced_unknown:
        warnings.append(
            "State records reference undeclared body ids: "
            + ", ".join(str(b) for b in referenced_unknown)
        )

    for w in warnings:
        _log.warning("MLC content: %s", w)

    return warnings
