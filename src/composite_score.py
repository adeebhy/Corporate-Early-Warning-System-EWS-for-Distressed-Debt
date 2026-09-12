"""
composite_score.py
--------------------
Combines fundamental forensics, statistical scores (Z''-EM, Ohlson), and
alternative warning flags into a single Early Warning rating. Deliberately
NOT a black-box weighted average -- it's a transparent point system so a
credit officer can see exactly which components drove the rating.

Point system (0-100, higher = more distressed):
  - Altman Z''-EM zone: Distress=30, Grey=15, Safe=0
  - Ohlson probability of distress: scaled 0-25
  - ICR < 1.5x: +15 (below 1.0x: +25 instead)
  - CFO/EBITDA < 0.5: +10 (below 0: +20 instead)
  - Cash flow divergence flag: +10
  - DuPont leverage-masking flag: +10
  - NLP alternative warning flags: +5 per high-severity (cap +20), +2 per medium (cap +10)
"""
from src.altman_zscore import ZScoreInputs, compute_all_variants
from src.ohlson_oscore import OScoreInputs, ohlson_o_score
from src.ratios import cash_flow_conversion, interest_coverage_ratio


def compute_ews_score(z_inputs: ZScoreInputs, o_inputs: OScoreInputs,
                        ebit: float, interest_expense: float, cfo: float, ebitda: float,
                        cash_flow_divergence: dict = None, dupont_flag: dict = None,
                        nlp_summary: dict = None) -> dict:
    points = 0
    breakdown = {}

    z_variants = compute_all_variants(z_inputs)
    z_em = z_variants.get("z_double_prime_em")
    if z_em and z_em.get("zone"):
        zone_points = dict(Distress=30, Grey=15, Safe=0)[z_em["zone"]]
        points += zone_points
        breakdown["altman_z_em"] = dict(score=z_em["score"], zone=z_em["zone"], points=zone_points)

    o_result = ohlson_o_score(o_inputs)
    o_points = round(25 * min(o_result["probability_of_distress"], 1.0), 1)
    points += o_points
    breakdown["ohlson_o_score"] = dict(score=o_result["o_score"],
                                          probability=o_result["probability_of_distress"], points=o_points)

    icr = interest_coverage_ratio(ebit, interest_expense)
    icr_points = 25 if (icr is not None and icr < 1.0) else (15 if (icr is not None and icr < 1.5) else 0)
    points += icr_points
    breakdown["interest_coverage_ratio"] = dict(value=icr, points=icr_points)

    cfc = cash_flow_conversion(cfo, ebitda)
    cfc_points = 20 if (cfc is not None and cfc < 0) else (10 if (cfc is not None and cfc < 0.5) else 0)
    points += cfc_points
    breakdown["cash_flow_conversion"] = dict(value=cfc, points=cfc_points)

    if cash_flow_divergence and cash_flow_divergence.get("flag"):
        points += 10
        breakdown["cash_flow_divergence_flag"] = dict(triggered=True, points=10)

    if dupont_flag and dupont_flag.get("flag"):
        points += 10
        breakdown["dupont_leverage_masking_flag"] = dict(triggered=True, points=10)

    if nlp_summary:
        nlp_points = min(5 * nlp_summary.get("n_high_severity", 0), 20) + min(2 * nlp_summary.get("n_medium_severity", 0), 10)
        points += nlp_points
        breakdown["nlp_alternative_flags"] = dict(**nlp_summary, points=nlp_points)

    points = min(points, 100)
    if points >= 60:
        rating = "High Risk -- Distressed / Near-Default Signal"
    elif points >= 35:
        rating = "Elevated Risk -- Watchlist"
    elif points >= 15:
        rating = "Moderate Risk -- Monitor"
    else:
        rating = "Low Risk"

    return dict(total_score=round(points, 1), rating=rating, breakdown=breakdown,
                z_score_variants=z_variants, ohlson_detail=o_result)
