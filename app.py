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
from src.pdf_extract import extract_from_pdf
from src.screener_fetch import fetch_company_live, parse_pasted_screener_text

st.set_page_config(page_title="Corporate Early Warning System", layout="wide")
st.title("Corporate Early Warning System for Distressed Debt")
st.caption("Fundamental forensics + Altman Z-Score + Ohlson O-Score + NLP filing scan -> a transparent, "
           "explainable distress rating for any company you enter.")

with st.expander("How to use this / what it is", expanded=False):
    st.markdown("""
Three ways to get a company's numbers in -- pick whichever works for you:

1. **Fetch by screener.in code** -- type a company's screener.in code (e.g. `TCS`, `TMCV`, `INFY`) and the
   app tries to fetch its financials automatically over the internet. Works from a normal home/office
   connection; if it's blocked (corporate firewall, anti-bot protection), a paste-text fallback is built in.
2. **Upload a PDF** -- upload an annual report or financial statement PDF and key line items are extracted
   automatically. **Always check the extracted numbers** -- PDF layouts vary a lot, and the exact source
   line is shown for every value so you can verify nothing was misread before trusting the score.
3. **Manual entry** -- type numbers in yourself, or override anything the automated methods got wrong.

All figures should be in the same currency/units -- the model only uses ratios, so units cancel out as
long as you're consistent.
""")

# ---------------------------------------------------------------------------
# STEP 1: Automated data acquisition (screener.in fetch, PDF upload, or skip)
# ---------------------------------------------------------------------------
st.sidebar.header("1. Get Company Data (automated)")
input_mode = st.sidebar.radio("Input method", ["Fetch by screener.in code", "Upload PDF", "Manual entry only"])

fetched = {}

if input_mode == "Fetch by screener.in code":
    code = st.sidebar.text_input("screener.in company code (e.g. TCS, TMCV, INFY)", "")
    consolidated = st.sidebar.checkbox("Consolidated figures", value=True)
    if st.sidebar.button("Fetch") and code.strip():
        with st.sidebar:
            with st.spinner("Fetching..."):
                result = fetch_company_live(code.strip(), consolidated=consolidated)
        if result.get("success"):
            fetched = result
            n = len([k for k in result if not k.startswith("_") and k not in ("success", "source_url")])
            st.sidebar.success(f"Fetched {n} fields from screener.in.")
        else:
            st.sidebar.error(f"Live fetch failed: {result.get('error')}")
            st.sidebar.info(result.get("hint", ""))
            if result.get("url_to_open_manually"):
                st.sidebar.markdown(f"[Open the page manually]({result['url_to_open_manually']}) and "
                                      f"paste the Balance Sheet/P&L/Cash Flow sections below:")
    pasted = st.sidebar.text_area("...or paste screener.in page text here (guaranteed-working fallback)", height=120)
    if pasted.strip():
        fetched = parse_pasted_screener_text(pasted)
        st.sidebar.success(f"Parsed {len([k for k in fetched if not k.startswith('_')])} fields from pasted text.")
        if fetched.get("_extraction_note"):
            st.sidebar.caption(fetched["_extraction_note"])

elif input_mode == "Upload PDF":
    uploaded = st.sidebar.file_uploader("Upload annual report / financial statement PDF", type=["pdf"])
    if uploaded is not None:
        with st.sidebar:
            with st.spinner("Extracting financial line items from PDF..."):
                pdf_result = extract_from_pdf(uploaded)
        st.sidebar.success(f"Found {pdf_result['n_fields_found']}/{pdf_result['n_fields_total']} fields.")
        if pdf_result["missing_fields"]:
            st.sidebar.warning(f"Not found (enter manually below): {', '.join(pdf_result['missing_fields'])}")
        with st.sidebar.expander("Review extracted values (please verify!)", expanded=True):
            for field, ctx in pdf_result["context"].items():
                st.write(f"**{field}** = {pdf_result['extracted'][field]:,.2f}")
                st.caption(f"page {ctx['page']}: \"{ctx['line'][:90]}\"")
        fetched = dict(pdf_result["extracted"])

if fetched:
    st.sidebar.warning("Fields below are pre-filled from automated extraction -- double-check anything "
                        "that looks wrong before computing the score.")


def pre(*keys, default=0.0):
    """Returns the first matching pre-fetched/extracted value found under any of the given key aliases."""
    for k in keys:
        if k in fetched and fetched[k] is not None:
            return float(fetched[k])
    return default


st.sidebar.header("2. Review / Complete Company Financials")
with st.sidebar:
    company_name = st.text_input("Company name (optional)", "")
    is_emerging_market = st.checkbox("Emerging market company (recommended for India)", value=True)
    is_public = st.checkbox("Publicly listed (has a market value of equity)", value=True)

    st.subheader("Balance Sheet")
    total_assets = st.number_input("Total Assets", value=pre("total_assets", default=1000.0), min_value=0.01)
    total_liabilities = st.number_input("Total Liabilities", value=pre("total_liabilities", default=600.0), min_value=0.0)
    current_assets = st.number_input("Current Assets", value=pre("current_assets", default=400.0), min_value=0.0)
    current_liabilities = st.number_input("Current Liabilities", value=pre("current_liabilities", default=250.0), min_value=0.0)
    working_capital = current_assets - current_liabilities
    retained_earnings = st.number_input("Retained Earnings", value=pre("retained_earnings", "reserves", default=200.0))
    default_book_equity = pre("total_equity", default=(total_assets - total_liabilities))
    book_value_equity = st.number_input("Book Value of Equity", value=default_book_equity)
    market_value_equity = st.number_input("Market Value of Equity (if public)", value=800.0) if is_public else None
    receivables = st.number_input("Trade Receivables", value=pre("receivables", default=120.0), min_value=0.0)
    payables = st.number_input("Trade Payables", value=pre("payables", default=100.0), min_value=0.0)
    inventory = st.number_input("Inventory", value=pre("inventory", default=80.0), min_value=0.0)

    st.subheader("Income Statement")
    sales = st.number_input("Sales / Revenue", value=pre("sales", default=1200.0), min_value=0.01)
    cogs = st.number_input("Cost of Goods Sold", value=pre("expenses", default=800.0), min_value=0.0)
    ebit = st.number_input("EBIT", value=pre("ebit", "operating_profit", default=150.0))
    ebitda = st.number_input("EBITDA", value=pre("ebitda", "operating_profit", default=200.0))
    interest_expense = st.number_input("Interest Expense", value=pre("interest_expense", "interest", default=40.0), min_value=0.01)
    net_income = st.number_input("Net Income (current year)", value=pre("net_income", "net_profit", default=80.0))
    net_income_prior = st.number_input("Net Income (prior year)", value=70.0)
    net_income_2yr_ago = st.number_input("Net Income (2 years ago, for CFO trend)", value=60.0)

    st.subheader("Cash Flow")
    cfo = st.number_input("Cash Flow from Operations (CFO)", value=pre("cfo", default=110.0))
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
