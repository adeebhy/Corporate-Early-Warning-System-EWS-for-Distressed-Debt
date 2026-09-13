"""
beneish_mscore.py
-------------------
Beneish (1999) 8-variable M-Score for detecting earnings manipulation,
coefficients verified against the original model as widely cited:

M = -4.84 + 0.920*DSRI + 0.528*GMI + 0.404*AQI + 0.892*SGI + 0.115*DEPI
    - 0.172*SGAI + 4.679*TATA - 0.327*LVGI

Cutoff: M > -1.78 is the commonly used modern practitioner threshold for
flagging likely manipulation (Beneish's original 1999 paper cited -2.22;
-1.78 is the more commonly applied cutoff in current practice and is used
as the default here, with -2.22 also reported for context).

Why this belongs next to Ohlson in a distress-detection tool: corporate
defaults are very often preceded by a period of earnings manipulation
(Satyam, Enron, Wirecard are the textbook cases). A high M-Score is an
EARLIER warning than a low Altman/Ohlson score, since manipulation
typically starts while the accounting-based scores still look acceptable.
"""
from dataclasses import dataclass


@dataclass
class BeneishInputs:
    receivables_t: float; receivables_t1: float
    sales_t: float; sales_t1: float
    cogs_t: float; cogs_t1: float
    current_assets_t: float; current_assets_t1: float
    ppe_t: float; ppe_t1: float
    securities_t: float; securities_t1: float
    total_assets_t: float; total_assets_t1: float
    depreciation_t: float; depreciation_t1: float
    sga_t: float; sga_t1: float
    net_income_t: float
    cfo_t: float
    current_liabilities_t: float; current_liabilities_t1: float
    long_term_debt_t: float; long_term_debt_t1: float


def compute_beneish_mscore(i: BeneishInputs) -> dict:
    dsri = (i.receivables_t / i.sales_t) / (i.receivables_t1 / i.sales_t1)

    gm_t = (i.sales_t - i.cogs_t) / i.sales_t
    gm_t1 = (i.sales_t1 - i.cogs_t1) / i.sales_t1
    gmi = gm_t1 / gm_t

    aqi_t = 1 - (i.current_assets_t + i.ppe_t + i.securities_t) / i.total_assets_t
    aqi_t1 = 1 - (i.current_assets_t1 + i.ppe_t1 + i.securities_t1) / i.total_assets_t1
    aqi = aqi_t / aqi_t1 if aqi_t1 != 0 else float("nan")

    sgi = i.sales_t / i.sales_t1

    depr_rate_t = i.depreciation_t / (i.ppe_t + i.depreciation_t)
    depr_rate_t1 = i.depreciation_t1 / (i.ppe_t1 + i.depreciation_t1)
    depi = depr_rate_t1 / depr_rate_t if depr_rate_t != 0 else float("nan")

    sgai = (i.sga_t / i.sales_t) / (i.sga_t1 / i.sales_t1)

    tata = (i.net_income_t - i.cfo_t) / i.total_assets_t

    lvgi_t = (i.current_liabilities_t + i.long_term_debt_t) / i.total_assets_t
    lvgi_t1 = (i.current_liabilities_t1 + i.long_term_debt_t1) / i.total_assets_t1
    lvgi = lvgi_t / lvgi_t1 if lvgi_t1 != 0 else float("nan")

    m = (-4.84 + 0.920 * dsri + 0.528 * gmi + 0.404 * aqi + 0.892 * sgi
         + 0.115 * depi - 0.172 * sgai + 4.679 * tata - 0.327 * lvgi)

    flagged = m > -1.78

    contributions = dict(DSRI=0.920 * dsri, GMI=0.528 * gmi, AQI=0.404 * aqi, SGI=0.892 * sgi,
                          DEPI=0.115 * depi, SGAI=-0.172 * sgai, TATA=4.679 * tata, LVGI=-0.327 * lvgi)
    top_driver = max(contributions, key=contributions.get)

    return dict(
        m_score=round(m, 4), flagged_as_likely_manipulator=bool(flagged),
        cutoff_used=-1.78, alternate_original_cutoff=-2.22,
        components=dict(DSRI=round(dsri, 4), GMI=round(gmi, 4), AQI=round(aqi, 4), SGI=round(sgi, 4),
                          DEPI=round(depi, 4), SGAI=round(sgai, 4), TATA=round(tata, 4), LVGI=round(lvgi, 4)),
        weighted_contributions={k: round(v, 4) for k, v in contributions.items()},
        top_positive_driver=top_driver,
        interpretation_note=("A screening flag, not proof of fraud -- Beneish's model was calibrated on "
                              "US public manufacturers and produces false positives for legitimately "
                              "fast-growing firms. TATA is the most heavily weighted variable and the "
                              "single strongest signal in Beneish's original research: persistent "
                              "positive accruals that never convert to cash."),
    )
