"""
india_signals.py
------------------
Three India-specific early warning signals that sit outside standard
Western accounting-based models but are heavily weighted by Indian credit
analysts and rating agencies in practice.

1. PROMOTER PLEDGE TRACKER: promoters pledging shares as loan collateral is
   one of the most reliable precursors to distress in Indian mid/large-caps
   -- it signals promoter-level liquidity stress that often precedes
   company-level stress. Flagged at >20% of promoter holding (a commonly
   cited threshold in Indian equity research), escalating above 50%.

2. CREDIT RATING DRIFT: parses a rating history and flags a 2-notch (or
   greater) downgrade within a 12-month window -- CRISIL/ICRA/CARE
   downgrades of this speed are themselves major market-moving events and a
   standard "instant escalation" trigger in real credit monitoring desks.

3. CONTINGENT LIABILITIES TO NET WORTH: off-balance-sheet exposures (tax
   disputes under appeal, group-entity guarantees) that don't show up in any
   accounting ratio above but can convert to real liabilities overnight
   (group-company guarantee webs are a recurring theme in major Indian
   defaults, IL&FS included).
"""
import datetime


RATING_SCALE = ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-",
                "BB+", "BB", "BB-", "B+", "B", "B-", "C", "D"]
RATING_NOTCH = {r: i for i, r in enumerate(RATING_SCALE)}


def promoter_pledge_flag(pledged_pct_of_promoter_holding: float) -> dict:
    if pledged_pct_of_promoter_holding >= 50:
        severity, message = "high", "Over 50% of promoter holding pledged -- severe promoter-level liquidity stress signal."
    elif pledged_pct_of_promoter_holding >= 20:
        severity, message = "medium", "Promoter pledge exceeds the commonly used 20% early-warning threshold."
    else:
        severity, message = "none", "Promoter pledge below the 20% threshold."
    return dict(pledged_pct=pledged_pct_of_promoter_holding, flagged=pledged_pct_of_promoter_holding >= 20,
                severity=severity, message=message)


def rating_drift_flag(rating_history: list) -> dict:
    """rating_history: list of dicts [{"date": "2024-01-15", "rating": "AA-", "agency": "CRISIL"}, ...],
    any order. Flags a 2+ notch drop within any 12-month rolling window."""
    parsed = []
    for entry in rating_history:
        rating = entry["rating"].upper().strip()
        if rating not in RATING_NOTCH:
            continue
        date = entry["date"] if isinstance(entry["date"], datetime.date) else datetime.date.fromisoformat(entry["date"])
        parsed.append(dict(date=date, rating=rating, notch=RATING_NOTCH[rating], agency=entry.get("agency", "")))
    parsed.sort(key=lambda x: x["date"])

    flagged_events = []
    for i, current in enumerate(parsed):
        window_start = current["date"] - datetime.timedelta(days=365)
        prior_in_window = [p for p in parsed[:i] if p["date"] >= window_start]
        if not prior_in_window:
            continue
        best_prior_notch = min(p["notch"] for p in prior_in_window)
        notch_drop = current["notch"] - best_prior_notch
        if notch_drop >= 2:
            flagged_events.append(dict(
                date=str(current["date"]), from_rating=RATING_SCALE[best_prior_notch],
                to_rating=current["rating"], notches_dropped=notch_drop, agency=current["agency"],
            ))

    return dict(flagged=len(flagged_events) > 0, n_events=len(flagged_events), events=flagged_events,
                current_rating=parsed[-1]["rating"] if parsed else None,
                message=(f"{len(flagged_events)} rapid-downgrade event(s) detected (>=2 notches within 12 months)."
                          if flagged_events else "No rapid multi-notch downgrade detected in the provided history."))


def contingent_liabilities_flag(contingent_liabilities: float, net_worth: float) -> dict:
    if net_worth <= 0:
        return dict(ratio=None, flagged=True, severity="high",
                     message="Net worth is zero or negative -- any contingent liability is a severe concern.")
    ratio = contingent_liabilities / net_worth
    if ratio >= 0.5:
        severity, message = "high", f"Contingent liabilities are {ratio*100:.0f}% of net worth -- very high hidden-leverage exposure."
    elif ratio >= 0.25:
        severity, message = "medium", f"Contingent liabilities are {ratio*100:.0f}% of net worth -- elevated; monitor guarantee/dispute developments."
    else:
        severity, message = "none", f"Contingent liabilities are {ratio*100:.0f}% of net worth -- within a typically unremarkable range."
    return dict(ratio=round(ratio, 4), flagged=ratio >= 0.25, severity=severity, message=message)
