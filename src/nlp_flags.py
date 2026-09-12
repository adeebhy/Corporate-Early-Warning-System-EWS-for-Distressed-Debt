"""
nlp_flags.py
-------------
Regex/keyword-based scanner for the "alternative warning flags": auditor
qualifications, promoter share pledge spikes, and delayed filing penalties.
Paste any filing/announcement text and it flags and quotes the specific
matching language -- no live scraping required since the user supplies the
text directly.

Rule-based rather than a trained classifier deliberately: filing language
for these events is highly formulaic (auditors, exchanges, and company
secretaries use fairly standardized phrasing precisely because these are
regulatory disclosures), so a well-built keyword/regex layer is both more
auditable and more precise here than a black-box model would be -- a credit
committee can see exactly which phrase tripped the flag.
"""
import re
from dataclasses import dataclass


@dataclass
class FlagMatch:
    category: str
    severity: str
    matched_text: str
    explanation: str


AUDITOR_QUALIFICATION_PATTERNS = [
    (r"\b(qualified opinion|adverse opinion|disclaimer of opinion)\b", "high",
     "Auditor issued a qualified/adverse/disclaimer opinion -- the strongest auditor-level red flag."),
    (r"\bemphasis of matter\b.{0,80}\b(going concern|material uncertainty)\b", "high",
     "Emphasis of Matter paragraph specifically citing going-concern doubt."),
    (r"\bgoing concern\b", "high", "Going concern language present in the filing."),
    (r"\bresign(ed|ation)\b.{0,60}\bauditor\b|\bauditor\b.{0,60}\bresign(ed|ation)\b", "high",
     "Auditor resignation -- a serious, often sudden red flag (auditors rarely resign without reason)."),
    (r"\bmaterial weakness(es)?\b.{0,60}\binternal (financial )?control", "medium",
     "Material weakness in internal financial controls disclosed."),
    (r"\bunable to obtain sufficient (and )?appropriate audit evidence\b", "high",
     "Auditor states they could not obtain sufficient audit evidence -- often precedes a disclaimer."),
]

PLEDGE_PATTERNS = [
    (r"\bpromoter[s]?\b.{0,60}\bpledg(ed|e|ing)\b", "high",
     "Promoter share pledging activity disclosed -- rising pledge levels often signal promoter-level liquidity stress."),
    (r"\bencumbrance[d]?\b.{0,60}\bpromoter\b|\bpromoter\b.{0,60}\bencumbra", "medium",
     "Promoter shareholding encumbrance disclosed."),
    (r"\binvocation of pledge\b", "high", "Pledge invocation -- lender has exercised rights over pledged shares, a severe signal."),
    (r"\b(\d{1,3}(\.\d+)?)\s*%\s*.{0,40}\bpledged\b", "medium", "Specific pledge percentage disclosed -- check magnitude and trend."),
]

FILING_DELAY_PATTERNS = [
    (r"\bdelay(ed)? in filing\b|\blate filing\b", "medium", "Delayed/late filing disclosed."),
    (r"\bpenalty\b.{0,60}\b(delay|non-?compliance|late filing)\b", "high",
     "Regulatory penalty for delayed filing or non-compliance -- a concrete enforcement action."),
    (r"\bstruck off\b|\bshow[- ]cause notice\b", "high", "Show-cause notice or striking-off action from the regulator."),
    (r"\bsuspension of trading\b|\btrading suspended\b", "high", "Trading suspension -- an exchange-level enforcement action."),
]

ALL_PATTERNS = dict(auditor_qualification=AUDITOR_QUALIFICATION_PATTERNS,
                     promoter_pledge=PLEDGE_PATTERNS, filing_delay=FILING_DELAY_PATTERNS)


def scan_filing_text(text: str) -> list:
    matches = []
    for category, patterns in ALL_PATTERNS.items():
        for pattern, severity, explanation in patterns:
            for m in re.finditer(pattern, text, flags=re.IGNORECASE):
                start = max(0, m.start() - 40)
                end = min(len(text), m.end() + 40)
                snippet = text[start:end].strip().replace("\n", " ")
                matches.append(FlagMatch(category=category, severity=severity,
                                           matched_text=f"...{snippet}...", explanation=explanation))
    return matches


def summarize_flags(matches: list) -> dict:
    n_high = sum(1 for m in matches if m.severity == "high")
    n_medium = sum(1 for m in matches if m.severity == "medium")
    categories_hit = sorted(set(m.category for m in matches))
    return dict(n_flags=len(matches), n_high_severity=n_high, n_medium_severity=n_medium,
                categories_hit=categories_hit,
                overall_alert_level="high" if n_high > 0 else ("medium" if n_medium > 0 else "none"))
