"""
ohlson_oscore.py
------------------
Ohlson (1980) 9-factor logit bankruptcy model, coefficients verified against
the original paper as commonly cited:

O = -1.32 - 0.407*SIZE + 6.03*TLTA - 1.43*WCTA + 0.0757*CLCA
    - 1.72*OENEG - 2.37*NITA - 1.83*FFO_TL + 0.285*INTWO - 0.521*CHIN

P(bankruptcy) = exp(O) / (1 + exp(O))

SIZE = log(Total Assets / price-level index). The original 1980 index was a
GNP price-level deflator normalized to 1968=100 -- a dated, US-specific
series. This implementation defaults the index to 1.0 (i.e., SIZE = log(TA)
in raw currency units), which is the common practical simplification used
by most modern calculators, and exposes the index as an optional parameter
for anyone who wants to apply a real price-level adjustment. This is an
explicit simplification, not a hidden one.

FFO (funds from operations) is approximated here as CFO (cash flow from
operations) if a separate FFO figure isn't available -- a standard practical
substitution, since the two are usually close for non-financial companies
and FFO is not separately reported under most accounting standards used
outside the US.

Interpretation: O=0 is the formula's own "even odds" midpoint (P=0.5), but
because bankruptcy is rare in the population Ohlson estimated on, many
practitioners use a MUCH lower probability cutoff (commonly cited figures
range from ~3.8% to ~50% depending on the source and how false-positive-averse
the use case is) rather than literally 0.5. This module reports the raw
score and probability and lets the user choose their own operating threshold
rather than picking one for them.
"""
from dataclasses import dataclass
import numpy as np


@dataclass
class OScoreInputs:
    total_assets: float
    total_liabilities: float
    working_capital: float
    current_liabilities: float
    current_assets: float
    net_income: float
    cfo_or_ffo: float
    net_income_prior_year: float
    net_loss_last_two_years: bool
    price_level_index: float = 1.0


def ohlson_o_score(i: OScoreInputs) -> dict:
    ta, tl = i.total_assets, i.total_liabilities
    size = np.log(ta / i.price_level_index) if ta > 0 else 0.0
    tlta = tl / ta if ta else 0.0
    wcta = i.working_capital / ta if ta else 0.0
    clca = i.current_liabilities / i.current_assets if i.current_assets else 0.0
    oeneg = 1.0 if tl > ta else 0.0
    nita = i.net_income / ta if ta else 0.0
    ffo_tl = i.cfo_or_ffo / tl if tl else 0.0
    intwo = 1.0 if i.net_loss_last_two_years else 0.0
    ni, ni_prior = i.net_income, i.net_income_prior_year
    chin = (ni - ni_prior) / (abs(ni) + abs(ni_prior)) if (abs(ni) + abs(ni_prior)) > 0 else 0.0

    o = (-1.32 - 0.407 * size + 6.03 * tlta - 1.43 * wcta + 0.0757 * clca
         - 1.72 * oeneg - 2.37 * nita - 1.83 * ffo_tl + 0.285 * intwo - 0.521 * chin)
    prob = float(np.exp(o) / (1 + np.exp(o)))

    return dict(
        o_score=round(float(o), 4), probability_of_distress=round(prob, 4),
        components=dict(SIZE=round(size, 4), TLTA=round(tlta, 4), WCTA=round(wcta, 4),
                          CLCA=round(clca, 4), OENEG=oeneg, NITA=round(nita, 4),
                          FFO_TL=round(ffo_tl, 4), INTWO=intwo, CHIN=round(chin, 4)),
    )
