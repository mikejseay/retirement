"""Income tax bracket utilities.

This module provides a simple progressive tax calculator given a list
of brackets like:
    [{"start": 0, "end": 11925, "rate": 0.10}, ...]

All amounts are in *nominal* dollars for that tax year. Inflation
adjustments (if any) should be done by the caller.
"""
from dataclasses import dataclass
from typing import List, Optional

@dataclass(frozen=True)
class TaxBracket:
    start: float
    end: Optional[float]  # None means no upper bound
    rate: float           # e.g., 0.22 for 22%

def compute_tax(taxable_income: float, brackets: List[TaxBracket]) -> float:
    """Compute tax owed under progressive brackets.

    Args:
        taxable_income: income subject to ordinary brackets (>=0).
        brackets: ordered low-to-high list of TaxBracket.

    Returns:
        Total tax in dollars.
    """
    if taxable_income <= 0:
        return 0.0

    tax = 0.0
    for b in brackets:
        lower = b.start
        upper = float('inf') if b.end is None else b.end
        if taxable_income <= lower:
            break
        amount_in_bracket = min(taxable_income, upper) - lower
        if amount_in_bracket > 0:
            tax += amount_in_bracket * b.rate
    return tax

# Default brackets parsed from the spreadsheet (can be overridden)
DEFAULT_BRACKETS: List[TaxBracket] = [
    TaxBracket(start=0, end=11925, rate=0.1),
    TaxBracket(start=11925, end=48475, rate=0.12),
    TaxBracket(start=48475, end=103350, rate=0.22),
    TaxBracket(start=103350, end=197300, rate=0.24),
    TaxBracket(start=197300, end=250000, rate=0.32),
    TaxBracket(start=250000, end=500000, rate=0.35),
    TaxBracket(start=500000, end=None, rate=0.37),
]
