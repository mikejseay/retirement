from retirement_planner import PlannerInputs, simulate, to_dataframe
from income_tax import DEFAULT_BRACKETS
from irmaa import DEFAULT_BRACKETS as IRMAA_DEFAULT

inputs = PlannerInputs(
    start_year=2025,
    start_age=71,
    start_trad_ira=1000000.0,
    start_roth_ira=100_000.0,  # adjust if you have a known starting Roth balance
)

# Manual entries from spreadsheet-like columns B and C
roth_conversions = {2025: 10000.0}
extra_dists = {2025: 42500.0, 2026: 44000.0, 2027: 5000.0, 2028: 5000.0}

rows = simulate(inputs, years=10, roth_conversions=roth_conversions, extra_trad_distributions=extra_dists)
df = to_dataframe(rows)
print(df.head(10).to_string(index=False))
