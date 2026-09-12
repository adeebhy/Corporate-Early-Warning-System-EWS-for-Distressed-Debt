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
Enter a company's figures in the sidebar (all in the same currency/units —
₹ crore, $ millions, whatever's convenient, since only ratios are used) and
the four tabs update live: DuPont & Ratios, Statistical Scores, Filing Scan,
and Composite Rating.

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
data/
  case_studies.py         # real IL&FS case + illustrative reference points
app.py                    # interactive Streamlit UI
```
