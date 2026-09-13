"""
src/pdf_extract.py
------------------
Extracts fundamental financial metrics from uploaded corporate annual report /
financial statement PDFs using regex pattern matching over text streams.
"""

import re
from typing import Any, Dict
from pypdf import PdfReader


def _clean_number(text: str) -> float | None:
    if not text:
        return None
    cleaned = re.sub(r"[^\d.-]", "", text.strip())
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_from_pdf(uploaded_file) -> Dict[str, Any]:
    """
    Extracts core financial statement metrics from an uploaded PDF stream.
    """
    reader = PdfReader(uploaded_file)
    pages_text = []
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages_text.append((idx + 1, text))

    # Field aliases mapped to common statement line labels
    field_patterns = {
        "total_assets": [
            r"total\s+assets",
            r"total\s+non-current\s+assets\s*\+\s*total\s+current\s+assets",
        ],
        "total_liabilities": [
            r"total\s+liabilities",
            r"total\s+debt",
            r"total\s+borrowings",
        ],
        "current_assets": [
            r"total\s+current\s+assets",
            r"current\s+assets",
        ],
        "current_liabilities": [
            r"total\s+current\s+liabilities",
            r"current\s+liabilities",
        ],
        "retained_earnings": [
            r"retained\s+earnings",
            r"other\s+equity",
            r"reserves\s+and\s+surplus",
        ],
        "total_equity": [
            r"total\s+equity",
            r"shareholders['\s]+funds",
            r"equity\s+share\s+capital",
        ],
        "sales": [
            r"revenue\s+from\s+operations",
            r"total\s+revenue",
            r"sales",
        ],
        "expenses": [
            r"total\s+expenses",
            r"cost\s+of\s+materials\s+consumed",
        ],
        "ebit": [
            r"operating\s+profit",
            r"profit\s+before\s+tax\s+and\s+finance\s+costs",
            r"ebit",
        ],
        "ebitda": [
            r"ebitda",
            r"operating\s+profit\s+before\s+working\s+capital",
        ],
        "interest_expense": [
            r"finance\s+costs",
            r"interest\s+expense",
            r"interest",
        ],
        "net_income": [
            r"profit\s+for\s+the\s+period",
            r"profit\s+for\s+the\s+year",
            r"net\s+profit",
            r"net\s+income",
        ],
        "receivables": [
            r"trade\s+receivables",
            r"sundry\s+debtors",
        ],
        "payables": [
            r"trade\s+payables",
            r"sundry\s+creditors",
        ],
        "inventory": [
            r"inventories",
            r"inventory",
            r"stock-in-trade",
        ],
        "cfo": [
            r"net\s+cash\s+(?:flow\s+)?from\s+operating\s+activities",
            r"cash\s+generated\s+from\s+operations",
        ],
    }

    extracted: Dict[str, float] = {}
    context: Dict[str, Dict[str, Any]] = {}
    target_fields = list(field_patterns.keys())

    # Scan pages sequentially for pattern matches
    for field, patterns in field_patterns.items():
        matched = False
        for page_num, text in pages_text:
            if matched:
                break
            for line in text.split("\n"):
                line_clean = line.strip()
                if not line_clean:
                    continue

                for pat in patterns:
                    regex = rf"(?i)\b{pat}\b.*?([\(\[\d][\d,\.\(\)\]\-]+)"
                    m = re.search(regex, line_clean)
                    if m:
                        val_str = m.group(1)
                        # Handle accounting parentheses as negative values: (123.45)
                        if val_str.startswith("(") and val_str.endswith(")"):
                            val_str = "-" + val_str[1:-1]

                        val = _clean_number(val_str)
                        if val is not None:
                            extracted[field] = val
                            context[field] = {
                                "page": page_num,
                                "line": line_clean,
                            }
                            matched = True
                            break
                if matched:
                    break

    missing_fields = [f for f in target_fields if f not in extracted]

    return {
        "extracted": extracted,
        "context": context,
        "missing_fields": missing_fields,
        "n_fields_found": len(extracted),
        "n_fields_total": len(target_fields),
    }
