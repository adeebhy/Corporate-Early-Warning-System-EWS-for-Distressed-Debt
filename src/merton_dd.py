"""
merton_dd.py
-------------
Merton (1974) structural credit model / KMV Distance-to-Default. Treats
equity as a call option on the firm's assets (Black-Scholes-Merton), with
strike = face value of debt. Unlike Altman/Ohlson (accounting-based, lag
indicators updated only when financials are filed), Merton DD is MARKET-
implied and updates every trading day as the stock price and its volatility
move.

THE CORE PROBLEM: asset value V_A and asset volatility sigma_V are not
directly observable (only equity value E and equity volatility sigma_E are,
from the stock market). Solving for them requires the system of two
simultaneous equations:

    E = V_A * N(d1) - D * exp(-r*T) * N(d2)                    (Black-Scholes call value)
    sigma_E * E = N(d1) * sigma_V * V_A                          (Ito's lemma: equity vol from asset vol)

where d1 = (ln(V_A/D) + (r + 0.5*sigma_V^2)*T) / (sigma_V*sqrt(T)), d2 = d1 - sigma_V*sqrt(T).

This module solves that system numerically (fixed-point iteration on sigma_V,
the standard practical approach also used by the original KMV methodology),
then computes:

    DD = (ln(V_A/D) + (mu - 0.5*sigma_V^2)*T) / (sigma_V*sqrt(T))
    PD = Phi(-DD)          [theoretical Merton default probability]

`mu` (expected asset return) is a genuinely separate input from `r`
(risk-free rate used inside the option-pricing system): the option-pricing
equations use the risk-neutral rate r, but DD itself is a REAL-WORLD
default probability, so it should use the actual expected return on assets,
not r. Conflating mu and r is a common source of error in DIY Merton DD
implementations, so keeping them separate and independently adjustable here
is deliberate (defaults mu = r as the common simplification when a better
estimate isn't available).

Debt default point D follows the standard KMV convention:
    D = Short-Term Debt + 0.5 * Long-Term Debt
(the empirical finding that firms typically default when asset value falls
to roughly this level, not the full face value of all debt).
"""
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq
from dataclasses import dataclass
import yfinance as yf


@dataclass
class MertonInputs:
    market_cap: float
    equity_volatility: float
    short_term_debt: float
    long_term_debt: float
    risk_free_rate: float = 0.07
    time_horizon: float = 1.0
    expected_asset_return: float = None


def default_point(short_term_debt: float, long_term_debt: float) -> float:
    return short_term_debt + 0.5 * long_term_debt


def _bs_equity_value(V: float, sigma_V: float, D: float, r: float, T: float) -> float:
    if V <= 0 or sigma_V <= 0:
        return 0.0
    d1 = (np.log(V / D) + (r + 0.5 * sigma_V ** 2) * T) / (sigma_V * np.sqrt(T))
    d2 = d1 - sigma_V * np.sqrt(T)
    return V * norm.cdf(d1) - D * np.exp(-r * T) * norm.cdf(d2)


def _bs_d1(V: float, sigma_V: float, D: float, r: float, T: float) -> float:
    return (np.log(V / D) + (r + 0.5 * sigma_V ** 2) * T) / (sigma_V * np.sqrt(T))


def solve_asset_value_and_volatility(E: float, sigma_E: float, D: float, r: float, T: float,
                                       max_iter: int = 200, tol: float = 1e-8) -> dict:
    V = E + D
    sigma_V = sigma_E * E / (E + D)

    for iteration in range(max_iter):
        def objective(V_guess):
            return _bs_equity_value(V_guess, sigma_V, D, r, T) - E

        lo, hi = D * 0.5, (E + D) * 5
        try:
            V_new = brentq(objective, lo, hi, xtol=1e-6)
        except ValueError:
            V_new = brentq(objective, D * 0.01, (E + D) * 20, xtol=1e-6)

        d1 = _bs_d1(V_new, sigma_V, D, r, T)
        sigma_V_new = sigma_E * E / (norm.cdf(d1) * V_new)

        if abs(V_new - V) < tol * V and abs(sigma_V_new - sigma_V) < tol:
            V, sigma_V = V_new, sigma_V_new
            break
        V, sigma_V = V_new, sigma_V_new

    return dict(asset_value=V, asset_volatility=sigma_V, iterations=iteration + 1,
                converged=iteration < max_iter - 1)


def compute_merton_dd(i: MertonInputs) -> dict:
    E, sigma_E = i.market_cap, i.equity_volatility
    D = default_point(i.short_term_debt, i.long_term_debt)
    r, T = i.risk_free_rate, i.time_horizon
    mu = i.expected_asset_return if i.expected_asset_return is not None else r

    if E <= 0 or D <= 0 or sigma_E <= 0:
        return dict(error="market_cap, default_point, and equity_volatility must all be positive")

    solved = solve_asset_value_and_volatility(E, sigma_E, D, r, T)
    V_A, sigma_V = solved["asset_value"], solved["asset_volatility"]

    dd = (np.log(V_A / D) + (mu - 0.5 * sigma_V ** 2) * T) / (sigma_V * np.sqrt(T))
    pd_theoretical = float(norm.cdf(-dd))

    return dict(
        asset_value=round(V_A, 2), asset_volatility=round(sigma_V, 4),
        default_point=round(D, 2), distance_to_default=round(float(dd), 3),
        probability_of_default=round(pd_theoretical, 6),
        leverage_ratio=round(D / V_A, 4),
        solver_converged=solved["converged"], solver_iterations=solved["iterations"],
        note=("Theoretical Merton PD via Phi(-DD). Real KMV maps DD to an EMPIRICAL default "
              "frequency (EDF) table built from historical default data at each DD level, since "
              "actual default rates deviate from the theoretical normal-distribution assumption "
              "(fatter tails in practice) -- that empirical mapping isn't reproduced here since it "
              "requires KMV's proprietary historical default database; the theoretical PD is "
              "directionally useful but will generally understate true default risk at low DD "
              "compared to the empirical EDF."),
    )

def generate_merton_explanation(company_name: str, merton_result: dict) -> str:
    """
    Generates plain-language credit analyst commentary explaining
    why Distance-to-Default (DD) and PD reached their specific values.
    """
    dd = merton_result.get("distance_to_default", 0.0)
    pd_val = merton_result.get("probability_of_default", 0.0) * 100
    leverage = merton_result.get("leverage_ratio", 0.0) * 100
    va = merton_result.get("asset_value", 0.0)
    dp = merton_result.get("default_point", 0.0)
    vol = merton_result.get("asset_volatility", 0.0) * 100

    name = company_name.strip() if company_name.strip() else "The company"

    # Case 1: Ultra-safe / Deleveraged / Asset-heavy
    if dd >= 6.0:
        commentary = (
            f"**Why is {name}'s Distance-to-Default so high ({dd:.2f}σ)?**\n\n"
            f"- **Negligible Leverage Burden:** Market-implied assets (₹{va:,.0f}) tower over the "
            f"effective default boundary (₹{dp:,.0f}). Debt makes up just **{leverage:.1f}%** of the firm's total economic value.\n"
            f"- **Solvency Buffer:** The firm's enterprise value would have to plummet by more than "
            f"**{100 - leverage:.1f}%** before its asset base breaches debt commitments.\n"
            f"- **Why PD displays 0.00%:** In a standard normal distribution $\\Phi(-DD)$, any Z-score past $5.0\\sigma$ "
            f"drops below $10^{{-7}}$. At {dd:.2f}σ, Gaussian probability evaluates to less than $10^{{-30}}$, which floating-point "
            f"precision rounds directly to zero. In actual commercial lending (e.g. Moody's KMV EDF), a minimum regulatory floor of "
            f"~0.03% (3 bps) is applied because statistical models do not account for extreme external shocks (fraud, sudden regulatory bans)."
        )

    # Case 2: Standard Investment Grade / Low Risk
    elif dd >= 3.0:
        commentary = (
            f"**What does {name}'s score of {dd:.2f}σ signify?**\n\n"
            f"- **Healthy Solvency Coverage:** Implied assets of ₹{va:,.0f} offer a comfortable cushion against "
            f"the default point of ₹{dp:,.0f} (leverage stands at **{leverage:.1f}%**).\n"
            f"- **Manageable Volatility:** Solved asset volatility is **{vol:.1f}%**, meaning the asset base is reasonably "
            f"stable and unlikely to erode toward default within the 1-year horizon."
        )

    # Case 3: Watchlist / Grey Zone
    elif dd >= 1.5:
        commentary = (
            f"**⚠️ Watchlist Alert for {name} ({dd:.2f}σ):**\n\n"
            f"- **Narrowing Cushion:** Leverage has climbed to **{leverage:.1f}%** (Default Point: ₹{dp:,.0f} vs. Assets: ₹{va:,.0f}).\n"
            f"- **Vulnerability to Volatility:** Given an asset volatility of **{vol:.1f}%**, an equity price drawdown or "
            f"earnings contraction could quickly push the company into distress territory."
        )

    # Case 4: Distress / Near-Default
    else:
        commentary = (
            f"**🚨 High Distress Signal for {name} ({dd:.2f}σ):**\n\n"
            f"- **Extreme Debt Overhang:** Debt obligations represent **{leverage:.1f}%** of the firm's economic value.\n"
            f"- **High Probability of Default:** Market pricing reflects a 1-year default probability of **{pd_val:.2f}%**. "
            f"The asset cushion is critically thin relative to near-term debt maturities."
        )

    return commentary

def get_live_equity_volatility(ticker: str, fallback_vol: float = 0.35) -> float:
    """
    Fetches 1 year of daily close data from Yahoo Finance
    and computes annualized historical volatility.
    """
    if not ticker:
        return fallback_vol

    # Try National Stock Exchange (.NS) then Bombay Stock Exchange (.BO)
    for suffix in [".NS", ".BO"]:
        symbol = f"{ticker.strip().upper()}{suffix}"
        try:
            df = yf.download(symbol, period="1y", interval="1d", progress=False)
            if df is not None and len(df) > 60:
                # Handle MultiIndex columns returned by newer yfinance versions
                if "Close" in df.columns:
                    closes = df["Close"]
                    if hasattr(closes, "iloc") and closes.ndim > 1:
                        closes = closes.iloc[:, 0]
                    returns = np.log(closes / closes.shift(1)).dropna()
                    annualized_vol = float(returns.std() * np.sqrt(252))
                    if 0.05 <= annualized_vol <= 2.5:
                        return annualized_vol
        except Exception:
            continue

    return fallback_vol
