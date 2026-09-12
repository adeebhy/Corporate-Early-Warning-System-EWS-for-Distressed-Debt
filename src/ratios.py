"""
ratios.py
---------
The "fundamental forensics" ratio set: cash flow conversion, interest
coverage, and working capital stress.
"""
import numpy as np


def cash_flow_conversion(cfo: float, ebitda: float) -> float:
    """CFO/EBITDA. A ratio well below 1.0 (persistently) means profits aren't
    translating into cash -- often the earliest, hardest-to-fake forensic
    warning sign of distress."""
    if ebitda == 0:
        return None
    return round(cfo / ebitda, 4)


def interest_coverage_ratio(ebit: float, interest_expense: float) -> float:
    """ICR = EBIT / Interest Expense. Below 1.5x is a commonly used
    early-warning threshold; below 1.0x means the company cannot service its
    debt from operating earnings at all."""
    if interest_expense == 0:
        return None
    return round(ebit / interest_expense, 4)


def working_capital_stress(current_assets: float, current_liabilities: float,
                             receivables: float, payables: float, inventory: float,
                             sales: float, cogs: float) -> dict:
    """Current/quick ratio and the cash conversion cycle. A LENGTHENING cash
    conversion cycle is a classic pre-distress working-capital stress signal."""
    current_ratio = current_assets / current_liabilities if current_liabilities else None
    quick_ratio = (current_assets - inventory) / current_liabilities if current_liabilities else None
    dso = (receivables / sales * 365) if sales else None
    dio = (inventory / cogs * 365) if cogs else None
    dpo = (payables / cogs * 365) if cogs else None
    ccc = (dso + dio - dpo) if all(v is not None for v in [dso, dio, dpo]) else None
    return dict(
        current_ratio=round(current_ratio, 3) if current_ratio is not None else None,
        quick_ratio=round(quick_ratio, 3) if quick_ratio is not None else None,
        days_sales_outstanding=round(dso, 1) if dso is not None else None,
        days_inventory_outstanding=round(dio, 1) if dio is not None else None,
        days_payables_outstanding=round(dpo, 1) if dpo is not None else None,
        cash_conversion_cycle=round(ccc, 1) if ccc is not None else None,
    )


def cash_flow_divergence_flag(net_income_history: list, cfo_history: list) -> dict:
    """Flags reported net income growing while operating cash flow diverges
    downward -- the single most-cited forensic red flag in distress case studies."""
    if len(net_income_history) < 2 or len(cfo_history) < 2:
        return dict(flag=False, reason="insufficient history")
    ni_growth = (net_income_history[-1] / net_income_history[0] - 1) if net_income_history[0] else 0
    cfo_growth = (cfo_history[-1] / cfo_history[0] - 1) if cfo_history[0] else 0
    divergence = ni_growth - cfo_growth
    flag = bool(ni_growth > 0 and cfo_growth < 0)
    return dict(flag=flag, net_income_growth_pct=round(ni_growth * 100, 1),
                cfo_growth_pct=round(cfo_growth * 100, 1), divergence_pp=round(divergence * 100, 1),
                reason=("Reported net income growing while operating cash flow is DECLINING -- "
                        "a classic accrual-quality red flag.") if flag else "No divergence flag.")
