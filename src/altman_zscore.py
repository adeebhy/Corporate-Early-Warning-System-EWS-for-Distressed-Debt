"""
altman_zscore.py
------------------
All major Altman Z-Score variants, formulas verified against Altman's
original and follow-on papers (1968, 1983, 1995):

  Z  (1968, public manufacturers):   1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
  Z' (1983, private companies):      0.717*X1 + 0.847*X2 + 3.107*X3 + 0.420*X4 + 0.998*X5
  Z''(1995, non-manufacturers):      6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4
  Z''-EM (1995, emerging markets):   3.25 + 6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4

X1 = Working Capital / Total Assets
X2 = Retained Earnings / Total Assets
X3 = EBIT / Total Assets
X4 = Market (Z) or Book (Z', Z'', Z''-EM) Value of Equity / Total Liabilities
X5 = Sales / Total Assets (dropped in Z'' / Z''-EM)

For India / other emerging markets, Z''-EM is the appropriate model (Altman
explicitly developed it for non-US, non-manufacturing contexts), so this is
the default recommendation in the composite score -- but all four are
computed since the underlying ratios are the same and the choice of variant
is a judgment call the user should be able to see and override.
"""
from dataclasses import dataclass


@dataclass
class ZScoreInputs:
    working_capital: float
    retained_earnings: float
    ebit: float
    total_assets: float
    total_liabilities: float
    sales: float
    market_value_equity: float = None   # for Z (public manufacturers)
    book_value_equity: float = None     # for Z', Z'', Z''-EM


def _x1(i): return i.working_capital / i.total_assets
def _x2(i): return i.retained_earnings / i.total_assets
def _x3(i): return i.ebit / i.total_assets
def _x5(i): return i.sales / i.total_assets


def altman_z(i: ZScoreInputs) -> dict:
    if i.market_value_equity is None:
        return dict(score=None, zone=None, note="market_value_equity required for the public-manufacturer Z model")
    x1, x2, x3, x5 = _x1(i), _x2(i), _x3(i), _x5(i)
    x4 = i.market_value_equity / i.total_liabilities
    z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
    zone = "Safe" if z > 2.99 else ("Grey" if z > 1.81 else "Distress")
    return dict(model="Z (public manufacturers)", score=round(z, 3), zone=zone,
                inputs=dict(X1=round(x1, 4), X2=round(x2, 4), X3=round(x3, 4), X4=round(x4, 4), X5=round(x5, 4)))


def altman_z_prime(i: ZScoreInputs) -> dict:
    if i.book_value_equity is None:
        return dict(score=None, zone=None, note="book_value_equity required for the private-company Z' model")
    x1, x2, x3, x5 = _x1(i), _x2(i), _x3(i), _x5(i)
    x4 = i.book_value_equity / i.total_liabilities
    z = 0.717 * x1 + 0.847 * x2 + 3.107 * x3 + 0.420 * x4 + 0.998 * x5
    zone = "Safe" if z > 2.9 else ("Grey" if z > 1.23 else "Distress")
    return dict(model="Z' (private companies)", score=round(z, 3), zone=zone,
                inputs=dict(X1=round(x1, 4), X2=round(x2, 4), X3=round(x3, 4), X4=round(x4, 4), X5=round(x5, 4)))


def altman_z_double_prime(i: ZScoreInputs, emerging_market: bool = False) -> dict:
    if i.book_value_equity is None:
        return dict(score=None, zone=None, note="book_value_equity required for the Z''/Z''-EM model")
    x1, x2, x3 = _x1(i), _x2(i), _x3(i)
    x4 = i.book_value_equity / i.total_liabilities
    z = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4
    label = "Z''-EM (emerging markets)"
    if emerging_market:
        z += 3.25
        zone = "Safe" if z > 5.85 else ("Grey" if z > 4.35 else "Distress")
    else:
        label = "Z'' (non-manufacturers)"
        zone = "Safe" if z > 2.6 else ("Grey" if z > 1.1 else "Distress")
    return dict(model=label, score=round(z, 3), zone=zone,
                inputs=dict(X1=round(x1, 4), X2=round(x2, 4), X3=round(x3, 4), X4=round(x4, 4)))


def compute_all_variants(i: ZScoreInputs) -> dict:
    return dict(
        z=altman_z(i) if i.market_value_equity else None,
        z_prime=altman_z_prime(i) if i.book_value_equity else None,
        z_double_prime=altman_z_double_prime(i, emerging_market=False) if i.book_value_equity else None,
        z_double_prime_em=altman_z_double_prime(i, emerging_market=True) if i.book_value_equity else None,
    )
