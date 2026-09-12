"""
app.py
------
Corporate Early Warning System -- interactive dashboard. Enter any company's
financial statement figures and get: DuPont ROE decomposition, cash flow/
coverage/working-capital ratios, all four Altman Z-Score variants, the
Ohlson O-Score probability of distress, a transparent composite EWS rating,
and an NLP scan of any filing/announcement text you paste in.

Run: streamlit run app.py
"""
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from src.dupont import dupont_decomposition, dupont_trend_flag
from src.ratios import cash_flow_conversion, interest_coverage_ratio, working_capital_stress, cash_flow_divergence_flag
from src.altman_zscore import ZScoreInputs, compute_all_variants
from src.ohlson_oscore import OScoreInputs, ohlson_o_score
from src.nlp_flags import scan_filing_text, summarize_flags
from src.composite_score import compute_ews_score

st.set_page_config(page_title="Corporate Early Warning System", layout="wide")
st.title("Corporate Early Warning System for Distressed Debt")
st.caption("Fundamental forensics + Altman Z-Score + Ohlson O-Score + NLP filing scan -> a transparent, "
           "explainable distress rating for any company you enter.")

with st.expander("How to use this / what it is", expanded=False):
    st.markdown("""
Enter a company's most recent annual (or TTM) financial-statement figures in the sidebar, then:
- **DuPont & Ratios** tab shows ROE decomposition and cash flow/coverage/working-capital forensics.
- **Statistical Scores** tab shows all four Altman Z-Score variants and the Ohlson O-Score.
- **Filing Scan** tab lets you paste any announcement/filing text to check for auditor qualification,
  promoter pledge, or delayed-filing red flags.
- **Composite Rating** tab combines everything into one transparent, point-by-point EWS score.

All figures should be in the same currency/units (e.g., all in ₹ crore, or all in $ millions) -- the
model only uses ratios, so units cancel out as long as you're consistent.
""")

with st.sidebar:
    st.header("Company Financials")
    company_name = st.text_input("Company name (optional)", "")
    is_emerging_market = st.checkbox("Emerging market company (recommended for India)", value=True)
    is_public = st.checkbox("Publicly listed (has a market value of equity)", value=True)

    st.subheader("Balance Sheet")
    total_assets = st.number_input("Total Assets", value=1000.0, min_value=0.01)
    total_liabilities = st.number_input("Total Liabilities", value=600.0, min_value=0.0)
    current_assets = st.number_input("Current Assets", value=400.0, min_value=0.0)
    current_liabilities = st.number_input("Current Liabilities", value=250.0, min_value=0.0)
    working_capital = current_assets - current_liabilities
    retained_earnings = st.number_input("Retained Earnings", value=200.0)
    book_value_equity = st.number_input("Book Value of Equity", value=total_assets - total_liabilities)
    market_value_equity = st.number_input("Market Value of Equity (if public)", value=800.0) if is_public else None
    receivables = st.number_input("Trade Receivables", value=120.0, min_value=0.0)
    payables = st.number_input("Trade Payables", value=100.0, min_value=0.0)
    inventory = st.number_input("Inventory", value=80.0, min_value=0.0)

    st.subheader("Income Statement")
    sales = st.number_input("Sales / Revenue", value=1200.0, min_value=0.01)
    cogs = st.number_input("Cost of Goods Sold", value=800.0, min_value=0.0)
    ebit = st.number_input("EBIT", value=150.0)
    ebitda = st.number_input("EBITDA", value=200.0)
    interest_expense = st.number_input("Interest Expense", value=40.0, min_value=0.01)
    net_income = st.number_input("Net Income (current year)", value=80.0)
    net_income_prior = st.number_input("Net Income (prior year)", value=70.0)
    net_income_2yr_ago = st.number_input("Net Income (2 years ago, for CFO trend)", value=60.0)

    st.subheader("Cash Flow")
    cfo = st.number_input("Cash Flow from Operations (CFO)", value=110.0)
    cfo_prior = st.number_input("CFO (prior year)", value=100.0)

    st.subheader("Filing / Announcement Text (optional)")
    filing_text = st.text_area("Paste any MCA/SEBI filing, auditor's report, or exchange announcement text",
                                 height=150, placeholder="Paste filing text here to scan for red flags...")

# --- Compute everything ---
z_inputs = ZScoreInputs(working_capital=working_capital, retained_earnings=retained_earnings, ebit=ebit,
                          total_assets=total_assets, total_liabilities=total_liabilities, sales=sales,
                          market_value_equity=market_value_equity, book_value_equity=book_value_equity)
o_inputs = OScoreInputs(total_assets=total_assets, total_liabilities=total_liabilities,
                          working_capital=working_capital, current_liabilities=current_liabilities,
                          current_assets=current_assets, net_income=net_income, cfo_or_ffo=cfo,
                          net_income_prior_year=net_income_prior,
                          net_loss_last_two_years=(net_income < 0 and net_income_prior < 0))

dupont = dupont_decomposition(net_income, sales, total_assets, book_value_equity)
dupont_history = pd.DataFrame([
    dict(period="t-1", **dupont_decomposition(net_income_prior, sales * 0.9, total_assets * 0.95, book_value_equity * 0.9)),
    dict(period="t0", **dupont),
])
dupont_flag = dupont_trend_flag(dupont_history)

cfc = cash_flow_conversion(cfo, ebitda)
icr = interest_coverage_ratio(ebit, interest_expense)
wc_stress = working_capital_stress(current_assets, current_liabilities, receivables, payables, inventory, sales, cogs)
cfd_flag = cash_flow_divergence_flag([net_income_2yr_ago, net_income_prior, net_income], [cfo_prior * 0.9, cfo_prior, cfo])

z_variants = compute_all_variants(z_inputs)
o_result = ohlson_o_score(o_inputs)

nlp_matches = scan_filing_text(filing_text) if filing_text.strip() else []
nlp_summary = summarize_flags(nlp_matches) if filing_text.strip() else None

ews = compute_ews_score(z_inputs, o_inputs, ebit, interest_expense, cfo, ebitda,
                          cash_flow_divergence=cfd_flag, dupont_flag=dupont_flag, nlp_summary=nlp_summary)

# --- Headline ---
st.divider()
c1, c2, c3 = st.columns(3)
c1.metric("Composite EWS Score", f"{ews['total_score']}/100")
c2.metric("Rating", ews["rating"].split(" -- ")[0])
z_em = z_variants["z_double_prime_em"]
c3.metric("Altman Z''-EM Zone", z_em["zone"] if z_em else "N/A")
st.markdown(f"**{ews['rating']}**" + (f" — {company_name}" if company_name else ""))

tab1, tab2, tab3, tab4 = st.tabs(["DuPont & Ratios", "Statistical Scores", "Filing Scan", "Composite Rating"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("DuPont ROE Decomposition")
        st.write(dupont)
        if dupont_flag["flag"]:
            st.warning(dupont_flag["reason"])
        else:
            st.success("No leverage-masked deterioration pattern detected.")

        st.subheader("Cash Flow Divergence")
        st.write(cfd_flag)
        if cfd_flag["flag"]:
            st.warning(cfd_flag["reason"])

    with col2:
        st.subheader("Coverage & Conversion")
        st.metric("Cash Flow Conversion (CFO/EBITDA)", cfc)
        st.metric("Interest Coverage Ratio (EBIT/Interest)", icr)
        if icr is not None and icr < 1.5:
            st.warning(f"ICR of {icr}x is below the 1.5x early-warning threshold.")
        st.subheader("Working Capital Stress")
        st.write(wc_stress)

with tab2:
    st.subheader("Altman Z-Score Variants")
    rows = []
    for key, label in [("z", "Z (public manufacturers)"), ("z_prime", "Z' (private companies)"),
                         ("z_double_prime", "Z'' (non-manufacturers)"), ("z_double_prime_em", "Z''-EM (emerging markets)")]:
        v = z_variants.get(key)
        if v and v.get("score") is not None:
            rows.append(dict(Model=label, Score=v["score"], Zone=v["zone"]))
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
    st.caption("Z''-EM is generally the most appropriate variant for Indian/emerging-market companies.")

    st.subheader("Ohlson O-Score")
    oc1, oc2 = st.columns(2)
    oc1.metric("O-Score", o_result["o_score"])
    oc2.metric("Probability of Distress", f"{o_result['probability_of_distress']*100:.1f}%")
    st.write("Component breakdown:", o_result["components"])

    fig, ax = plt.subplots(figsize=(6, 4))
    labels = [r["Model"] for r in rows]
    values = [r["Score"] for r in rows]
    colors = ["#2ca02c" if r["Zone"] == "Safe" else ("#ff7f0e" if r["Zone"] == "Grey" else "#d62728") for r in rows]
    ax.barh(labels, values, color=colors)
    ax.set_xlabel("Z-Score")
    st.pyplot(fig)

with tab3:
    st.subheader("Filing / Announcement Red-Flag Scan")
    if not filing_text.strip():
        st.info("Paste filing or announcement text in the sidebar to scan for red flags.")
    else:
        if nlp_summary["n_flags"] == 0:
            st.success("No auditor qualification, promoter pledge, or filing delay red flags detected.")
        else:
            st.error(f"{nlp_summary['n_flags']} flag(s) detected -- overall alert level: {nlp_summary['overall_alert_level'].upper()}")
            for m in nlp_matches:
                icon = "🔴" if m.severity == "high" else "🟠"
                st.markdown(f"{icon} **[{m.category}]** {m.explanation}")
                st.caption(m.matched_text)

with tab4:
    st.subheader("Composite EWS Score Breakdown")
    st.json(ews["breakdown"])
    st.caption("Transparent point system -- see README.md for the full scoring rubric. "
               "This is a decision-support tool, not a substitute for full credit underwriting.")
