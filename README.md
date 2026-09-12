# Corporate Early Warning System (EWS) for Distressed Debt

A practical, working distress-detection tool: enter any company's financial
statement figures and get DuPont ROE forensics, cash-flow/coverage/working-
capital stress ratios, all four Altman Z-Score variants, the Ohlson O-Score
probability of distress, an NLP scan of filing text for auditor/pledge/
delay red flags, and a transparent composite EWS rating — all in an
interactive Streamlit UI.

## Run it
```
pip install -r requirements.txt
streamlit run app.py
```
Three ways to get data in, chosen from the sidebar:
1. **Fetch by screener.in code** — type a company code (e.g. `TCS`, `TMCV`, `INFY`) and it fetches
   Balance Sheet/P&L/Cash Flow automatically over the internet.
2. **Upload PDF** — upload an annual report or financial statement PDF; key line items are extracted
   automatically, with the exact source line shown for every value so you can verify before scoring.
3. **Manual entry** — type numbers in, or override anything the automated methods missed/misread.

## Automated data acquisition — what's real, what to know

**screener.in fetch** (`src/screener_fetch.py`): a real HTTP scraper for Indian listed companies'
Balance Sheet/P&L/Cash Flow tables (data provider: C-MOTS Internet Technologies, no login required for
this data). **Tested and validated**: the parser correctly extracted all 13 matched line items from real
Tata Motors data pulled during development (Total Assets ₹52,309cr, Sales ₹87,197cr, Net Profit
₹4,187cr — all matched exactly). **Honesty note on what I could and couldn't test**: this sandboxed build
environment's outbound IP gets a 403 from screener.in's bot protection on direct HTTP requests (confirmed
via curl testing) — a sandbox-specific block, not a flaw in the scraper. It should work normally from your
own machine's regular internet connection. If it's ever blocked (corporate firewall, layout change, rate
limiting), a guaranteed-working fallback is built in: open the page yourself, copy the financial tables,
and paste the text in — it's parsed with the exact same validated logic.

*Usage terms*: review screener.in's Terms of Use before automated/bulk/commercial use — this is built for
individual, occasional lookups, not high-volume scraping.

**PDF extraction** (`src/pdf_extract.py`): regex + table extraction via `pdfplumber` over any uploaded
PDF. **Tested and validated** against a synthetic test annual report: found all 15/15 target line items
correctly. Real annual reports vary enormously in layout — multi-column, scanned images, inconsistent
naming — so this **always shows the exact extracted value and its source line for you to verify** rather
than silently trusting a number. Treat every extraction as a first draft, not a verified fact — a single
misread digit could produce a badly wrong distress score, so the review step isn't optional friction, it's
the responsible way to automate this.

## Methodology

**Fundamental forensics** (`src/dupont.py`, `src/ratios.py`): DuPont ROE
decomposition (net margin × asset turnover × equity multiplier) specifically
to catch **leverage-masked deterioration** — ROE holding steady while margin
falls and leverage rises, meaning "improvement" is coming from more debt,
not better operations. Plus cash flow conversion (CFO/EBITDA), interest
coverage (EBIT/interest expense), working capital stress (current/quick
ratio, cash conversion cycle), and a cash-flow-divergence flag (net income
growing while CFO is shrinking — the classic accrual-quality red flag).

**Statistical scoring** (`src/altman_zscore.py`, `src/ohlson_oscore.py`):
all four Altman Z-Score variants (Z, Z', Z'', Z''-EM) and the full 9-factor
Ohlson O-Score, coefficients verified against Altman's original papers
(1968/1983/1995) and Ohlson (1980) rather than assumed from memory:
```
Z''-EM = 3.25 + 6.56·X1 + 3.26·X2 + 6.72·X3 + 1.05·X4      (Altman 1995, emerging markets)
O = -1.32 - 0.407·SIZE + 6.03·TLTA - 1.43·WCTA + 0.0757·CLCA
    - 1.72·OENEG - 2.37·NITA - 1.83·FFO/TL + 0.285·INTWO - 0.521·CHIN     (Ohlson 1980)
```
Z''-EM is the default recommendation for Indian/emerging-market companies —
Altman explicitly developed this variant for non-US, non-manufacturing
contexts, unlike the original 1968 model built on US manufacturers.

**Alternative warning flags** (`src/nlp_flags.py`): regex/keyword scanning
of pasted filing or announcement text for auditor qualifications, promoter
pledge activity, and delayed-filing penalties — genuinely functional (paste
any real filing text) without needing live MCA/SEBI scraping.

**Composite score** (`src/composite_score.py`): a transparent point system
(0-100), not a black-box blend — every point is traceable to a specific
ratio, score zone, or flag, which matters more for a credit officer's trust
in the tool than squeezing out marginal accuracy from an opaque model.

## Validation

Real bulk historical default data (bankruptcy filing databases, MCA/SEBI
filings at scale) isn't reachable from this sandbox's network — the same
constraint as the other projects in this series. What's included instead:

**A real, verified case**: IL&FS Engineering & Construction, part of the
2018 IL&FS group collapse (India's largest infrastructure-financier default
in over a decade). Real, sourced total assets (₹1,630 cr), total liabilities
(₹4,820 cr), and negative book equity (-₹3,190 cr) — retrieved via search
from public financial-data aggregators — run through the model:

| Case | EWS Score | Rating | Ground truth |
|---|---|---|---|
| IL&FS Engineering & Construction | **90/100** | High Risk — Distressed | Defaulted (2018) |
| Illustrative healthy large-cap | 0/100 | Low Risk | N/A (reference point) |

Working capital, EBIT, and current asset/liability splits for the IL&FS case
are illustrative (not individually reported in the source), consistent with
the real totals — see `data/case_studies.py` for the exact caveat. Treat
this as a directional sanity check on a real, famous default, not a
large-sample statistical backtest.

## Honesty notes / limitations

- **No bulk backtest.** One real case + illustrative reference points, not
  a validated hit-rate across hundreds of real defaults — that needs bulk
  historical financial data this sandbox can't reach.
- **Ohlson's SIZE term uses a simplified price-level index** (defaults to
  1.0, i.e. raw log(total assets)) rather Ohlson's original 1968-indexed
  GNP deflator, which is dated and US-specific — the standard practical
  simplification, exposed as an adjustable parameter.
- **FFO is approximated as CFO** where a separate funds-from-operations
  figure isn't available (standard substitution for non-US reporting).
- **NLP scanner is regex/keyword-based**, not a trained classifier —
  deliberate, since filing language for these specific events is highly
  formulaic and a rule-based approach is more auditable for a compliance
  context (a credit committee can see exactly which phrase tripped a flag).
- **Composite score weights are a reasonable, transparent judgment call**,
  not fit against a labeled dataset (no bulk default data available) — treat
  the weighting as a documented starting point to recalibrate against your
  own portfolio's actual default history.
- **Decision-support tool, not a substitute for full credit underwriting**
  or professional forensic accounting review.

## Repo layout
```
src/
  dupont.py            # ROE decomposition + leverage-masking trend flag
  ratios.py             # CFO/EBITDA, ICR, working capital stress, CF divergence
  altman_zscore.py       # Z, Z', Z'', Z''-EM (coefficients verified)
  ohlson_oscore.py       # 9-factor Ohlson logit model (coefficients verified)
  nlp_flags.py            # regex scanner: auditor quals, pledges, filing delays
  composite_score.py      # transparent point-system EWS rating
  screener_fetch.py        # real screener.in scraper + paste-text fallback parser
  pdf_extract.py            # PDF financial statement line-item extraction
data/
  case_studies.py         # real IL&FS case + illustrative reference points
app.py                    # interactive Streamlit UI with 3 input modes
```
