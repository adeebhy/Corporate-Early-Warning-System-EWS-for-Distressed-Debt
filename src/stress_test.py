"""
stress_test.py
----------------
Forward-looking stress testing: shock interest rates, revenue, and gross
margin, then recompute Interest Coverage Ratio and Debt Service Coverage
Ratio under the stressed scenario to check for loan covenant breaches.

This is the one component in this project that is explicitly FORWARD-
LOOKING rather than backward-looking from reported financials: "the company
looks fine today, but does it survive a plausible bad scenario?"

DSCR = (EBITDA - Cash Taxes) / (Interest Expense + Scheduled Principal Repayment)
ICR (stressed) = Stressed EBIT / Stressed Interest Expense

Typical covenant thresholds (varies by loan agreement): DSCR >= 1.20x,
ICR >= 1.50x, used as defaults here.
"""
from dataclasses import dataclass


@dataclass
class StressTestBaseline:
    revenue: float
    gross_margin_pct: float
    other_operating_costs: float
    depreciation_amortization: float
    existing_debt: float
    current_interest_rate_pct: float
    scheduled_principal_repayment: float
    cash_tax_rate_pct: float = 0.25
    dscr_covenant: float = 1.20
    icr_covenant: float = 1.50


def _compute_metrics(revenue, gross_margin_pct, other_opex, da, interest_expense,
                       principal_repayment, tax_rate_pct):
    gross_profit = revenue * gross_margin_pct
    ebitda = gross_profit - other_opex
    ebit = ebitda - da
    pretax_income = max(ebit - interest_expense, 0)
    cash_taxes = pretax_income * tax_rate_pct
    icr = ebit / interest_expense if interest_expense > 0 else float("inf")
    dscr_numerator = ebitda - cash_taxes
    dscr_denominator = interest_expense + principal_repayment
    dscr = dscr_numerator / dscr_denominator if dscr_denominator > 0 else float("inf")
    return dict(revenue=round(revenue, 2), gross_profit=round(gross_profit, 2), ebitda=round(ebitda, 2),
                ebit=round(ebit, 2), interest_expense=round(interest_expense, 2), icr=round(icr, 3),
                dscr=round(dscr, 3), cash_taxes=round(cash_taxes, 2))


def run_stress_test(baseline: StressTestBaseline, rate_shock_bps: float = 0,
                      revenue_shock_pct: float = 0, margin_compression_bps: float = 0) -> dict:
    base_interest_expense = baseline.existing_debt * baseline.current_interest_rate_pct
    baseline_metrics = _compute_metrics(baseline.revenue, baseline.gross_margin_pct,
                                          baseline.other_operating_costs, baseline.depreciation_amortization,
                                          base_interest_expense, baseline.scheduled_principal_repayment,
                                          baseline.cash_tax_rate_pct)

    stressed_revenue = baseline.revenue * (1 + revenue_shock_pct / 100)
    stressed_margin = max(baseline.gross_margin_pct + margin_compression_bps / 10000, 0.0)
    stressed_rate = baseline.current_interest_rate_pct + rate_shock_bps / 10000
    stressed_interest_expense = baseline.existing_debt * stressed_rate

    stressed_metrics = _compute_metrics(stressed_revenue, stressed_margin, baseline.other_operating_costs,
                                          baseline.depreciation_amortization, stressed_interest_expense,
                                          baseline.scheduled_principal_repayment, baseline.cash_tax_rate_pct)

    dscr_breach = stressed_metrics["dscr"] < baseline.dscr_covenant
    icr_breach = stressed_metrics["icr"] < baseline.icr_covenant

    return dict(
        baseline=baseline_metrics, stressed=stressed_metrics,
        shocks_applied=dict(rate_shock_bps=rate_shock_bps, revenue_shock_pct=revenue_shock_pct,
                              margin_compression_bps=margin_compression_bps),
        dscr_covenant=baseline.dscr_covenant, icr_covenant=baseline.icr_covenant,
        dscr_breach=dscr_breach, icr_breach=icr_breach,
        any_covenant_breach=bool(dscr_breach or icr_breach),
        dscr_headroom=round(stressed_metrics["dscr"] - baseline.dscr_covenant, 3),
        icr_headroom=round(stressed_metrics["icr"] - baseline.icr_covenant, 3),
    )


def find_breaking_point(baseline: StressTestBaseline, shock_type: str, max_search: float = 2000) -> dict:
    """Finds the smallest shock magnitude (for one shock dimension at a time)
    at which a covenant breach first occurs -- a single "how much stress can
    this company absorb" number for a credit committee."""
    step = 5
    for magnitude in range(0, int(max_search), step):
        kwargs = {"rate_shock_bps": 0, "revenue_shock_pct": 0, "margin_compression_bps": 0}
        if shock_type == "rate_shock_bps":
            kwargs["rate_shock_bps"] = magnitude
        elif shock_type == "revenue_shock_pct":
            kwargs["revenue_shock_pct"] = -magnitude
        elif shock_type == "margin_compression_bps":
            kwargs["margin_compression_bps"] = -magnitude
        result = run_stress_test(baseline, **kwargs)
        if result["any_covenant_breach"]:
            return dict(shock_type=shock_type, breaking_magnitude=magnitude, result=result)
    return dict(shock_type=shock_type, breaking_magnitude=None,
                note=f"No breach found within the searched range (0 to {max_search}).")
