"""IRMAA (Medicare Part B) surcharge utilities.

Given MAGI and filing-status-specific brackets, returns the monthly surcharge
and annual surcharge for the year.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class IRMAABracket:
    start: float
    end: float | None  # None means no upper bound
    monthly_surcharge: float


def surcharge_for_magi(magi: float, brackets: list[IRMAABracket]) -> tuple[float, float]:
    for b in brackets:
        upper = float("inf") if b.end is None else b.end
        if b.start <= magi <= upper:
            return b.monthly_surcharge, b.monthly_surcharge * 12.0
    # If somehow below first bracket
    return 0.0, 0.0


# Default IRMAA brackets parsed from the spreadsheet (can be overridden)
DEFAULT_BRACKETS: list[IRMAABracket] = [
    IRMAABracket(start=0.0, end=None, monthly_surcharge=0.0),
    IRMAABracket(start=106011.0, end=None, monthly_surcharge=87.7),
    IRMAABracket(start=133001.0, end=None, monthly_surcharge=220.3),
    IRMAABracket(start=167000.0, end=None, monthly_surcharge=352.9),
    IRMAABracket(start=200001.0, end=None, monthly_surcharge=485.5),
    IRMAABracket(start=500000.0, end=None, monthly_surcharge=529.6999999999999),
]
