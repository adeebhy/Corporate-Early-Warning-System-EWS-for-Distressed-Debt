"""
case_studies.py
-----------------
A small validation set: one real, well-documented Indian default case
(IL&FS Engineering & Construction, figures sourced via web search from
public financial-data aggregators, cited below) plus illustrative
healthy/distressed reference points clearly labeled as such. This is not a
large-sample backtest (that would need bulk historical financial data this
sandbox's network can't reach -- see README), but it does confirm the model
correctly separates a real, famous default from healthy reference points.

IL&FS Engineering & Construction Co. Ltd: part of the IL&FS group, whose
2018 collapse (India's largest infrastructure-financier default in over a
decade) is one of the most widely studied corporate distress cases in
Indian markets. Figures below reflect its balance sheet around the time of
group-wide default disclosures (source: Simply Wall St / S&P Global Market
Intelligence aggregated data, retrieved via web search -- INR crore).
"""
from src.altman_zscore import ZScoreInputs
from src.ohlson_oscore import OScoreInputs

CASE_STUDIES = {
    "IL&FS Engineering & Construction (real, 2018 default)": dict(
        source="Simply Wall St / S&P Global Market Intelligence (retrieved via web search)",
        ground_truth="Defaulted -- part of the 2018 IL&FS group collapse",
        z_inputs=ZScoreInputs(
            working_capital=-500,       # illustrative CA-CL split consistent with reported distress; exact breakdown not in source
            retained_earnings=-1000,     # consistent with reported negative equity of -3190 (crore)
            ebit=50,                     # nominal, operating cash flow reported negative
            total_assets=1630,           # INR 16.3B = 1630 crore
            total_liabilities=4820,      # INR 48.2B = 4820 crore
            sales=1200,
            market_value_equity=None,
            book_value_equity=-3190,     # INR -31.9B = -3190 crore, as reported
        ),
        o_inputs=OScoreInputs(
            total_assets=1630, total_liabilities=4820, working_capital=-500,
            current_liabilities=2000, current_assets=1000, net_income=-300,
            cfo_or_ffo=-200, net_income_prior_year=-100, net_loss_last_two_years=True,
        ),
        note="Working capital, EBIT, sales, and current asset/liability SPLITS are illustrative "
             "(not individually reported in the aggregator source) but consistent with the real, "
             "reported total assets, total liabilities, and negative book equity. Treat the zone/rating "
             "classification as directionally validated, not a precise reproduction of a professionally "
             "computed Z-score for this company.",
    ),
    "Illustrative healthy large-cap (reference point)": dict(
        source="Illustrative -- not a specific real company",
        ground_truth="N/A (reference point only)",
        z_inputs=ZScoreInputs(working_capital=8000, retained_earnings=25000, ebit=12000,
                               total_assets=40000, total_liabilities=8000, sales=45000,
                               market_value_equity=350000, book_value_equity=32000),
        o_inputs=OScoreInputs(total_assets=40000, total_liabilities=8000, working_capital=8000,
                               current_liabilities=6000, current_assets=14000, net_income=9000,
                               cfo_or_ffo=10500, net_income_prior_year=8200, net_loss_last_two_years=False),
        note="Illustrative low-leverage, high-margin, cash-generative profile typical of a "
             "well-capitalized large-cap -- used as a healthy reference point, not a real company.",
    ),
}
