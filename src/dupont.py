"""
dupont.py
---------
3-step DuPont ROE decomposition:

    ROE = Net Profit Margin x Asset Turnover x Equity Multiplier
        = (Net Income / Sales) x (Sales / Total Assets) x (Total Assets / Equity)

Why this matters for an early-warning system: ROE can look STABLE or even
IMPROVING while the underlying quality deteriorates badly -- the classic
distress pattern is margin compression being masked by rising leverage
(equity multiplier climbing) rather than genuine operating improvement.
Decomposing ROE surfaces this even when the headline number hasn't moved yet.
"""

from typing import Any, Dict, List, Union
import numpy as np
import pandas as pd


def dupont_decomposition(
    net_income: float, sales: float, total_assets: float, equity: float
) -> Dict[str, Union[float, None]]:
    # Zero or missing denominators cannot be processed
    if not sales or not total_assets or not equity:
        return dict(
            net_margin=None,
            asset_turnover=None,
            equity_multiplier=None,
            roe=None,
        )

    net_margin = net_income / sales
    asset_turnover = sales / total_assets
    equity_multiplier = total_assets / equity

    # If equity is negative, mathematical ROE is distorted/unreliable for standard DuPont
    roe = net_margin * asset_turnover * equity_multiplier

    return dict(
        net_margin=round(float(net_margin), 4),
        asset_turnover=round(float(asset_turnover), 4),
        equity_multiplier=round(float(equity_multiplier), 4),
        roe=round(float(roe), 4),
        negative_equity=(equity < 0),
    )


def dupont_trend_flag(
    dupont_history: Union[pd.DataFrame, List[Dict[str, Any]], List[Any]]
) -> Dict[str, Union[bool, str]]:
    # Extract chronological boundary records (first = t-1, last = t0)
    if isinstance(dupont_history, pd.DataFrame):
        if len(dupont_history) < 2:
            return {"flag": False, "reason": "Insufficient historical periods for trend."}
        first = dupont_history.iloc[0]
        last = dupont_history.iloc[-1]
    elif isinstance(dupont_history, (list, tuple)):
        if len(dupont_history) < 2:
            return {"flag": False, "reason": "Insufficient historical periods for trend."}
        first = dupont_history[0]
        last = dupont_history[-1]
    else:
        return {"flag": False, "reason": "Invalid history format."}

    def get_val(item: Any, *keys: str) -> Union[float, None]:
        for k in keys:
            val = None
            if isinstance(item, (pd.Series, dict)):
                val = item.get(k)
            else:
                val = getattr(item, k, None)

            if val is not None and not pd.isna(val):
                try:
                    return float(val)
                except (ValueError, TypeError):
                    continue
        return None

    first_margin = get_val(first, "net_margin", "profit_margin", "net_profit_margin")
    last_margin = get_val(last, "net_margin", "profit_margin", "net_profit_margin")

    first_leverage = get_val(first, "equity_multiplier", "leverage")
    last_leverage = get_val(last, "equity_multiplier", "leverage")

    # Immediate red flag: Balance sheet insolvency / negative equity
    last_neg_equity = get_val(last, "negative_equity")
    if last_neg_equity or (last_leverage is not None and last_leverage < 0):
        return {
            "flag": True,
            "reason": "Severe capital distress: Negative book equity detected (equity multiplier < 0).",
        }

    # Verify required data points exist before proceeding
    if first_margin is None or last_margin is None:
        return {
            "flag": False,
            "reason": "Net margin data incomplete across historical periods.",
        }

    if first_leverage is None or last_leverage is None:
        return {
            "flag": False,
            "reason": "Leverage / Equity Multiplier data incomplete across historical periods.",
        }

    # Core EWS pattern: Net margin dropping while leverage expands
    margin_falling = last_margin < first_margin
    leverage_rising = last_leverage > first_leverage

    if margin_falling and leverage_rising:
        pct_margin_drop = ((first_margin - last_margin) / abs(first_margin)) * 100 if first_margin != 0 else 0.0
        pct_leverage_rise = ((last_leverage - first_leverage) / abs(first_leverage)) * 100 if first_leverage != 0 else 0.0
        return {
            "flag": True,
            "reason": (
                f"Margin compression masked by financial leverage: Net Margin dropped "
                f"from {first_margin*100:.2f}% to {last_margin*100:.2f}%, while Equity Multiplier "
                f"increased from {first_leverage:.2f}x to {last_leverage:.2f}x."
            ),
        }

    return {
        "flag": False,
        "reason": "No leverage-masked deterioration pattern detected.",
    }
