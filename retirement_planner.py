"""Retirement planner derived from the provided Excel model.

This is a faithful-as-possible conversion using the exposed sheet columns.
Key simplifying assumptions where the spreadsheet logic wasn't 100% explicit:

- RMDs use the IRS Uniform Lifetime Table (2023+) with first RMD at age 73.
- AGI = other_income + SSA (taxable portion proxy) + Roth conversions
    + extra Traditional IRA dists + RMD.
- Taxable income = max(AGI - standard_deduction - senior_deduction, 0).
- IRMAA is computed from MAGI≈AGI using the supplied brackets.
- Living expenses inflate annually.
- If net income (AGI - taxes - IRMAA) is less than living expenses, the gap is pulled from Roth.
- Traditional IRA balance evolves by: grow at investment_return, then subtract RMD, Roth conversion,
    and extra distributions.
- Roth IRA balance evolves by: grow at investment_return, add Roth conversion, then subtract any
    withdrawal to meet expenses.
- SSA benefit inflates annually; "factor_to_adjust_ssa" (from constants) can optionally scale it if
    desired.

The code is structured so you can replace any assumption with your own logic.
"""

from dataclasses import asdict, dataclass

from income_tax import DEFAULT_BRACKETS as DEFAULT_TAX_BRACKETS, TaxBracket, compute_tax
from irmaa import (
    DEFAULT_BRACKETS as DEFAULT_IRMAA_BRACKETS,
    IRMAABracket,
    surcharge_for_magi,
)

# TODO: can the calculator be programmed to recommend Trad IRA additional distributions?
# TODO: when LTC kicks in, living expenses probably decrease to some extent

# Minimal IRS Uniform Lifetime Table for ages 73..110 (2023+). Extend as needed.
UNIFORM_LIFETIME_DIVISORS = {
    73: 26.5,
    74: 25.5,
    75: 24.6,
    76: 23.7,
    77: 22.9,
    78: 22.0,
    79: 21.1,
    80: 20.2,
    81: 19.4,
    82: 18.5,
    83: 17.7,
    84: 16.8,
    85: 16.0,
    86: 15.2,
    87: 14.4,
    88: 13.7,
    89: 12.9,
    90: 12.2,
    91: 11.5,
    92: 10.8,
    93: 10.1,
    94: 9.5,
    95: 8.9,
    96: 8.4,
    97: 7.8,
    98: 7.3,
    99: 6.8,
    100: 6.4,
    101: 6.0,
    102: 5.6,
    103: 5.2,
    104: 4.9,
    105: 4.6,
    106: 4.3,
    107: 4.1,
    108: 3.9,
    109: 3.7,
    110: 3.5,
}


@dataclass
class PlannerInputs:
    start_year: int
    start_age: int
    start_trad_ira: float
    start_roth_ira: float = 0.0
    investment_return: float = 0.07
    inflation_rate: float = 0.03
    start_standard_deduction: float = 15750.0
    standard_deduction_growth: float = 0.022222222
    start_senior_deduction: float = 4530.0
    other_income: float = 7000.0
    start_ssa: float = 40000.0
    ssa_factor: float = 0.88
    start_living_expenses: float = 65000.0
    ltc_start_year: int | None = 2038
    ltc_start_cost: float = 100000.0
    rmd_start_age: int = 73

    tax_brackets: list[TaxBracket] | None = None
    irmaa_brackets: list[IRMAABracket] | None = None


@dataclass
class PlannerRow:
    year: int
    age: int
    trad_ira: float
    roth_ira: float
    rmd: float
    roth_conversion: float
    extra_trad_dist: float
    ssa: float
    agi: float
    std_deduction: float
    senior_deduction: float
    taxable_income: float
    tax: float
    magi: float
    irmaa_annual: float
    living_expenses: float
    amt_from_roth: float
    net_income: float  # AGI - tax - IRMAA


def rmd_for_age(age: int, balance: float, rmd_start_age: int = 73) -> float:
    """Compute RMD given age, using the uniform lifetime table."""
    if age < rmd_start_age:
        return 0.0
    divisor = UNIFORM_LIFETIME_DIVISORS.get(age)
    if divisor is None:
        # For ages beyond table, continue decreasing gently
        divisor = max(3.0, 26.5 - (age - 73) * 0.8)
    return balance / divisor


def simulate(
    inputs: PlannerInputs,
    years: int,
    roth_conversions: dict[int, float],
    extra_trad_distributions: dict[int, float],
    include_senior_deduction: bool = True,
) -> list[PlannerRow]:
    tb = inputs.tax_brackets or DEFAULT_TAX_BRACKETS
    ib = inputs.irmaa_brackets or DEFAULT_IRMAA_BRACKETS

    rows: list[PlannerRow] = []
    trad = float(inputs.start_trad_ira)
    roth = float(inputs.start_roth_ira)

    for i in range(years):
        year = inputs.start_year + i
        age = inputs.start_age + i

        # Inflation multipliers
        inflation_n = (1.0 + inputs.inflation_rate) ** i

        # Income components
        ssa = inputs.start_ssa * inflation_n * inputs.ssa_factor
        other_income = inputs.other_income  # keep constant; adjust if desired

        # Pre-distribution growth
        trad_growth = trad * inputs.investment_return
        roth_growth = roth * inputs.investment_return

        # RMD based on starting-year-end balance (pre-RMD)
        rmd = rmd_for_age(age, trad, inputs.rmd_start_age)

        # User choices
        roth_conv = float(roth_conversions.get(year, 0.0))
        extra_dist = float(extra_trad_distributions.get(year, 0.0))

        # Update balances after growth and moves
        trad_next = trad + trad_growth - rmd - roth_conv - extra_dist
        # We assume Roth conv is immediate & taxable in the same year
        # Roth withdrawals (to cover expenses) are applied below after tax calc
        roth_next = roth + roth_growth + roth_conv

        # AGI and deductions
        agi = max(0.0, other_income + ssa + rmd + roth_conv + extra_dist)
        std_ded = inputs.start_standard_deduction * ((1.0 + inputs.standard_deduction_growth) ** i)
        senior_ded = (
            inputs.start_senior_deduction if include_senior_deduction and age >= 65 else 0.0
        )

        taxable = max(0.0, agi - std_ded - senior_ded)
        tax = compute_tax(taxable, tb)
        magi = agi  # simplification; adjust if needed
        _, irmaa_annual = surcharge_for_magi(magi, ib)

        net_income = agi - tax - irmaa_annual

        # Expenses + LTC
        living = inputs.start_living_expenses * inflation_n
        if inputs.ltc_start_year and year >= inputs.ltc_start_year:
            living += inputs.ltc_start_cost * inflation_n

        # If net income insufficient, draw from Roth
        amt_from_roth = max(0.0, living - net_income)
        roth_next -= amt_from_roth

        row = PlannerRow(
            year=year,
            age=age,
            trad_ira=round(trad_next, 2),
            roth_ira=round(roth_next, 2),
            rmd=round(rmd, 2),
            roth_conversion=round(roth_conv, 2),
            extra_trad_dist=round(extra_dist, 2),
            ssa=round(ssa, 2),
            agi=round(agi, 2),
            std_deduction=round(std_ded, 2),
            senior_deduction=round(senior_ded, 2),
            taxable_income=round(taxable, 2),
            tax=round(tax, 2),
            magi=round(magi, 2),
            irmaa_annual=round(irmaa_annual, 2),
            living_expenses=round(living, 2),
            amt_from_roth=round(amt_from_roth, 2),
            net_income=round(net_income, 2),
        )
        rows.append(row)

        trad, roth = trad_next, roth_next

    return rows


def to_dataframe(rows: list[PlannerRow]):
    try:
        import pandas as pd
    except Exception:
        raise RuntimeError("pandas is required to build a DataFrame output")
    return pd.DataFrame([asdict(r) for r in rows])
