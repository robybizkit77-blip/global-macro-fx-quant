#!/usr/bin/env python3
"""Research-only Transmission & Conviction Layer V1.

This module classifies whether CB, front-end rates, relative 2Y and price
are transmitting an already-frozen macro direction. It never creates or
changes the macro bias and contains no fitted parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Optional

VALID_DIRS = {-1, 0, 1}
EVIDENCE_KEYS = (
    "cb_direction",
    "front_end_direction",
    "relative_2y_direction",
    "price_direction",
)


@dataclass(frozen=True)
class TransmissionInput:
    currency: str
    macro_direction: int
    cb_direction: Optional[int] = None
    front_end_direction: Optional[int] = None
    relative_2y_direction: Optional[int] = None
    price_direction: Optional[int] = None


@dataclass(frozen=True)
class TransmissionOutput:
    currency: str
    macro_direction: int
    layer_states: Dict[str, str]
    aligned_count: int
    divergent_count: int
    neutral_count: int
    missing_count: int
    coverage_count: int
    transmission_state: str
    conviction: str
    macro_bias_changed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _validate_direction(name: str, value: Optional[int]) -> None:
    if value is not None and value not in VALID_DIRS:
        raise ValueError(f"{name} must be one of -1, 0, +1, None; got {value!r}")


def _classify_layer(macro_direction: int, value: Optional[int]) -> str:
    if value is None:
        return "MISSING"
    if value == 0:
        return "NEUTRAL"
    if value == macro_direction:
        return "ALIGNED"
    return "DIVERGENT"


def evaluate(inp: TransmissionInput) -> TransmissionOutput:
    if not inp.currency or not isinstance(inp.currency, str):
        raise ValueError("currency must be a non-empty string")
    _validate_direction("macro_direction", inp.macro_direction)
    for key in EVIDENCE_KEYS:
        _validate_direction(key, getattr(inp, key))

    if inp.macro_direction == 0:
        states = {
            key: ("MISSING" if getattr(inp, key) is None else "NOT_EVALUATED")
            for key in EVIDENCE_KEYS
        }
        missing = sum(v == "MISSING" for v in states.values())
        coverage = len(EVIDENCE_KEYS) - missing
        return TransmissionOutput(
            currency=inp.currency.upper(),
            macro_direction=0,
            layer_states=states,
            aligned_count=0,
            divergent_count=0,
            neutral_count=0,
            missing_count=missing,
            coverage_count=coverage,
            transmission_state="MACRO_NEUTRAL_OR_WITHHELD",
            conviction="WITHHELD",
        )

    states = {key: _classify_layer(inp.macro_direction, getattr(inp, key)) for key in EVIDENCE_KEYS}
    aligned = sum(v == "ALIGNED" for v in states.values())
    divergent = sum(v == "DIVERGENT" for v in states.values())
    neutral = sum(v == "NEUTRAL" for v in states.values())
    missing = sum(v == "MISSING" for v in states.values())
    coverage = len(EVIDENCE_KEYS) - missing

    if coverage < 2:
        aggregate = "INSUFFICIENT_EVIDENCE"
        conviction = "WITHHELD"
    elif aligned >= 3 and divergent == 0:
        aggregate = "BROAD_CONFIRMATION"
        conviction = "HIGH"
    elif divergent >= 2 and divergent > aligned:
        aggregate = "DIVERGENCE"
        conviction = "LOW"
    elif aligned >= 2 and aligned > divergent:
        aggregate = "PARTIAL_CONFIRMATION"
        conviction = "MEDIUM"
    else:
        aggregate = "MIXED"
        conviction = "LOW"

    return TransmissionOutput(
        currency=inp.currency.upper(),
        macro_direction=inp.macro_direction,
        layer_states=states,
        aligned_count=aligned,
        divergent_count=divergent,
        neutral_count=neutral,
        missing_count=missing,
        coverage_count=coverage,
        transmission_state=aggregate,
        conviction=conviction,
    )


def _self_test() -> None:
    cases = [
        (
            TransmissionInput("CAD", 1, 1, 1, 1, 1),
            ("BROAD_CONFIRMATION", "HIGH", 4, 0),
        ),
        (
            TransmissionInput("JPY", -1, -1, -1, 0, None),
            ("PARTIAL_CONFIRMATION", "MEDIUM", 2, 0),
        ),
        (
            TransmissionInput("GBP", 1, 1, -1, 1, -1),
            ("MIXED", "LOW", 2, 2),
        ),
        (
            TransmissionInput("USD", -1, 1, 1, -1, 1),
            ("DIVERGENCE", "LOW", 1, 3),
        ),
        (
            TransmissionInput("EUR", 1, None, 1, None, None),
            ("INSUFFICIENT_EVIDENCE", "WITHHELD", 1, 0),
        ),
        (
            TransmissionInput("CHF", 0, 1, -1, None, 1),
            ("MACRO_NEUTRAL_OR_WITHHELD", "WITHHELD", 0, 0),
        ),
    ]

    for inp, expected in cases:
        out = evaluate(inp)
        aggregate, conviction, aligned, divergent = expected
        assert out.transmission_state == aggregate, (inp, out)
        assert out.conviction == conviction, (inp, out)
        assert out.aligned_count == aligned, (inp, out)
        assert out.divergent_count == divergent, (inp, out)
        assert out.macro_bias_changed is False
        assert out.macro_direction == inp.macro_direction

    try:
        evaluate(TransmissionInput("AUD", 2, 1, 1, 1, 1))
    except ValueError:
        pass
    else:
        raise AssertionError("invalid macro direction must fail")

    print("PASS transmission_conviction_layer_v1 self-test")


if __name__ == "__main__":
    _self_test()
