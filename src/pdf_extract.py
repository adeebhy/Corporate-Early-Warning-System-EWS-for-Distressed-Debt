"""
pdf_extract.py
----------------
Extracts financial statement line items from an uploaded annual report /
financial statement PDF using pdfplumber (text + table extraction) plus
regex line-item matching.

HONESTY NOTE, please read: real annual report PDFs vary enormously in
layout (multi-column, scanned images, inconsistent line-item naming across
companies and years, numbers in different units on different pages). This
extractor is a genuine best-effort tool, not a guaranteed-correct one -- it
is deliberately built to ALWAYS show you what it extracted for confirmation
before computing any score, rather than silently trusting a number that
might have been misread from a messy table. Treat every extracted value as
a first draft to verify, not a verified fact.
"""
import re
import pdfplumber

LINE_ITEM_PATTERNS = {
    "total_assets": [r"total\s+assets"],
    "total_liabilities": [r"total\s+liabilit(y|ies)", r"total\s+equity\s+and\s+liabilit"],
    "total_equity": [r"total\s+equity\b", r"shareholders?.?\s+funds?", r"net\s+worth"],
    "current_assets": [r"total\s+current\s+assets"],
    "current_liabilities": [r"total\s+current\s+liabilit"],
    "sales": [r"revenue\s+from\s+operations", r"total\s+revenue", r"net\s+sales", r"^\s*sales\b"],
    "ebitda": [r"\bebitda\b"],
    "ebit": [r"\bebit\b(?!da)", r"operating\s+profit", r"profit\s+before\s+interest\s+and\s+tax"],
    "interest_expense": [r"finance\s+cost", r"interest\s+expense"],
    "net_income": [r"profit\s+for\s+the\s+(year|period)", r"net\s+profit", r"profit\s+after\s+tax"],
    "cfo": [r"cash\s+(flow\s+)?(generated\s+from|from)\s+operating\s+activit"],
    "retained_earnings": [r"retained\s+earnings", r"surplus\s+in\s+(the\s+)?statement\s+of\s+profit"],
    "inventory": [r"\binventor(y|ies)\b"],
    "receivables": [r"trade\s+receivables"],
    "payables": [r"trade\s+payables"],
}

NUMBER_RE = re.compile(r"[-(]?[\d,]+\.?\d*[)]?")


def _extract_numbers_from_line(line: str) -> list:
    nums = []
    for match in NUMBER_RE.finditer(line):
        raw = match.group().replace(",", "")
        neg = raw.startswith("(") and raw.endswith(")")
        raw = raw.strip("()")
        try:
            val = float(raw)
            if val == 0 and len(raw) <= 1:
                continue
            nums.append(-val if neg else val)
        except ValueError:
            continue
    return nums


def extract_from_pdf(file_path_or_buffer) -> dict:
    """Scans every page's text line by line matching known line-item labels,
    pulling the FIRST number on that line (statements conventionally put the
    current-period figure first). Falls back to table extraction for any
    line items not found via plain text."""
    found = {}
    found_context = {}

    with pdfplumber.open(file_path_or_buffer) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            for line in text.split("\n"):
                line_lower = line.lower()
                for canonical, patterns in LINE_ITEM_PATTERNS.items():
                    if canonical in found:
                        continue
                    if any(re.search(p, line_lower) for p in patterns):
                        nums = _extract_numbers_from_line(line)
                        if nums:
                            found[canonical] = nums[0]
                            found_context[canonical] = dict(page=page_num + 1, line=line.strip())

            missing = [k for k in LINE_ITEM_PATTERNS if k not in found]
            if not missing:
                continue
            tables = page.extract_tables() or []
            for table in tables:
                for row in table:
                    if not row or not row[0]:
                        continue
                    label = str(row[0]).lower()
                    for canonical in list(missing):
                        if canonical in found:
                            continue
                        if any(re.search(p, label) for p in LINE_ITEM_PATTERNS[canonical]):
                            for cell in row[1:]:
                                if cell is None:
                                    continue
                                nums = _extract_numbers_from_line(str(cell))
                                if nums:
                                    found[canonical] = nums[0]
                                    found_context[canonical] = dict(page=page_num + 1, line=f"(table) {row}")
                                    break

    return dict(extracted=found, context=found_context,
                n_fields_found=len(found), n_fields_total=len(LINE_ITEM_PATTERNS),
                missing_fields=[k for k in LINE_ITEM_PATTERNS if k not in found])
