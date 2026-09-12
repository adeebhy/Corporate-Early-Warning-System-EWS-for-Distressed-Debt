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
import pandas as pd


def dupont_decomposition(net_income: float, sales: float, total_assets: float, equity: float) -> dict:
    if sales == 0 or total_assets == 0 or equity == 0:
        return dict(net_margin=None, asset_turnover=None, equity_multiplier=None, roe=None)
    net_margin = net_income / sales
    asset_turnover = sales / total_assets
    equity_multiplier = total_assets / equity
    roe = net_margin * asset_turnover * equity_multiplier
    return dict(net_margin=round(net_margin, 4), asset_turnover=round(asset_turnover, 4),
                equity_multiplier=round(equity_multiplier, 4), roe=round(roe, 4))


def dupont_trend_flag(history: pd.DataFrame) -> dict:
    """
    history: DataFrame with columns [period, net_margin, asset_turnover, equity_multiplier, roe],
    most recent period last. Flags the specific "leverage-masked deterioration"
    pattern: ROE flat/rising while net margin is falling AND equity multiplier is rising.
    """
    if len(history) < 2:
        return dict(flag=False, reason="insufficient history for trend analysis")
    first, last = history.iloc[0], history.iloc[-1]
    margin_falling = last.net_margin < first.net_margin
    leverage_rising = last.equity_multiplier > first.equity_multiplier * 1.1
    roe_masking = last.roe >= first.roe * 0.95  # roe held up despite the above

    flag = bool(margin_falling and leverage_rising and roe_masking)
    return dict(
        flag=flag,
        margin_change_pct=round((last.net_margin / first.net_margin - 1) * 100, 2) if first.net_margin else None,
        leverage_change_pct=round((last.equity_multiplier / first.equity_multiplier - 1) * 100, 2) if first.equity_multiplier else None,
        roe_change_pct=round((last.roe / first.roe - 1) * 100, 2) if first.roe else None,
        reason=("Net margin declining while leverage rises and ROE is held up by increased debt, "
                "not operating improvement -- a classic leverage-masked deterioration pattern.") if flag
                else "No leverage-masked deterioration pattern detected.",
    )
