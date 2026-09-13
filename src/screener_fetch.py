"""
src/screener_fetch.py
---------------------
Scrapes financial tables from screener.in and extracts both standard
EWS model inputs and comprehensive extended line items.
"""

import requests
from bs4 import BeautifulSoup
import re


def clean_number(text: str):
    if not text:
        return None
    # Remove commas, percentage signs, and whitespace
    cleaned = re.sub(r"[^\d.-]", "", text.strip())
    try:
        return float(cleaned)
    except ValueError:
        return None


def fetch_company_live(code: str, consolidated: bool = True) -> dict:
    code = code.strip().upper()
    url = f"https://www.screener.in/company/{code}/consolidated/" if consolidated else f"https://www.screener.in/company/{code}/"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code == 404 and consolidated:
            # Fallback to standalone if consolidated page doesn't exist
            url = f"https://www.screener.in/company/{code}/"
            resp = requests.get(url, headers=headers, timeout=12)

        if resp.status_code != 200:
            return {
                "success": False,
                "error": f"HTTP {resp.status_code} - Unable to reach screener.in",
                "url_to_open_manually": url,
                "hint": "Check if ticker symbol is correct or if IP is rate-limited."
            }

        return parse_screener_html(resp.text, source_url=url)

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "url_to_open_manually": url,
            "hint": "Connection error or timeout."
        }


def parse_screener_html(html_text: str, source_url: str = "") -> dict:
    soup = BeautifulSoup(html_text, "html.parser")
    data = {"success": True, "source_url": source_url}

    def extract_table(section_id):
        table_dict = {}
        section = soup.find("section", {"id": section_id})
        if not section:
            return table_dict

        table = section.find("table")
        if not table:
            return table_dict

        # Extract dates / headers
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        periods = headers[1:] if len(headers) > 1 else []

        for row in table.find_all("tr"):
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) >= 2:
                row_label = cols[0].strip().lower()
                row_label = re.sub(r"\s+", "_", row_label)
                row_label = re.sub(r"[+%/()&.-]", "", row_label).strip("_")

                # Grab latest period (last column) and T-1 (second to last)
                latest_val = clean_number(cols[-1])
                prior_val = clean_number(cols[-2]) if len(cols) > 2 else None

                table_dict[row_label] = latest_val
                if prior_val is not None:
                    table_dict[f"{row_label}_prior"] = prior_val

        return table_dict

    # 1. Parse all primary financial tables
    pl_data = extract_table("profit-loss")
    bs_data = extract_table("balance-sheet")
    cf_data = extract_table("cash-flow")
    ratio_data = extract_table("ratios")

    # 2. Extract Top Overview / Market Cap Cards
    overview = {}
    for li in soup.select("ul#top-ratios li"):
        name_elem = li.select_one(".name")
        val_elem = li.select_one(".value")
        if name_elem and val_elem:
            key = re.sub(r"[^\w]+", "_", name_elem.get_text(strip=True).lower()).strip("_")
            overview[key] = clean_number(val_elem.get_text(strip=True))

    # Merge all extracted metrics
    raw_all = {**overview, **pl_data, **bs_data, **cf_data, **ratio_data}

    # 3. Standardize keys for app.py and pre() matching
    mappings = {
        "sales": raw_all.get("sales"),
        "expenses": raw_all.get("expenses"),
        "operating_profit": raw_all.get("operating_profit"),
        "ebit": raw_all.get("operating_profit"),
        "ebitda": raw_all.get("operating_profit"),
        "interest_expense": raw_all.get("interest"),
        "net_income": raw_all.get("net_profit"),
        "net_income_prior": raw_all.get("net_profit_prior"),
        "total_assets": raw_all.get("total_assets"),
        "total_equity": (
            (raw_all.get("equity_capital") or 0.0) + (raw_all.get("reserves") or 0.0)
            if ("equity_capital" in raw_all or "reserves" in raw_all)
            else None
        ),
        "retained_earnings": raw_all.get("reserves"),
        "cfo": raw_all.get("cash_from_operating_activity"),
        "cfo_prior": raw_all.get("cash_from_operating_activity_prior"),
        "borrowings": raw_all.get("borrowings") or raw_all.get("total_debt"),
        "other_liabilities": raw_all.get("other_liabilities"),
        "market_cap": raw_all.get("market_cap"),
        "current_price": raw_all.get("current_price"),
        "roce": raw_all.get("roce"),
        "debtor_days": raw_all.get("debtor_days"),
        "inventory_days": raw_all.get("inventory_days"),
        "days_payable": raw_all.get("days_payable"),
        "working_capital_days": raw_all.get("working_capital_days"),
    }

    # Include all mapped keys and all raw parsed metrics
    for k, v in mappings.items():
        if v is not None:
            data[k] = v

    for k, v in raw_all.items():
        if k not in data and v is not None:
            data[k] = v

    return data


def parse_pasted_screener_text(pasted_text: str) -> dict:
    """
    Parses unstructured or tab-separated text copied and pasted
    directly from screener.in web pages.
    """
    if not pasted_text or not pasted_text.strip():
        return {}

    lines = pasted_text.strip().splitlines()
    data = {"success": True, "_extraction_note": "Parsed from pasted text"}
    raw_parsed = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Split by tabs or multiple spaces commonly produced when copying web tables
        parts = re.split(r"\t+|\s{2,}", line)
        if len(parts) >= 2:
            key_raw = parts[0].strip().lower()
            key = re.sub(r"\s+", "_", key_raw)
            key = re.sub(r"[+%/()&.-]", "", key).strip("_")

            # Extract the latest reported figure (last column) and prior figure if available
            vals = [clean_number(p) for p in parts[1:] if clean_number(p) is not None]
            if vals:
                raw_parsed[key] = vals[-1]
                if len(vals) > 1:
                    raw_parsed[f"{key}_prior"] = vals[-2]

    # Standardize extracted keys to match app.py expected keys
    mappings = {
        "sales": raw_parsed.get("sales"),
        "expenses": raw_parsed.get("expenses"),
        "operating_profit": raw_parsed.get("operating_profit"),
        "ebit": raw_parsed.get("operating_profit"),
        "ebitda": raw_parsed.get("operating_profit"),
        "interest_expense": raw_parsed.get("interest"),
        "net_income": raw_parsed.get("net_profit"),
        "net_income_prior": raw_parsed.get("net_profit_prior"),
        "total_assets": raw_parsed.get("total_assets"),
        "total_equity": (
            (raw_parsed.get("equity_capital") or 0.0) + (raw_parsed.get("reserves") or 0.0)
            if ("equity_capital" in raw_parsed or "reserves" in raw_parsed)
            else None
        ),
        "retained_earnings": raw_parsed.get("reserves"),
        "cfo": raw_parsed.get("cash_from_operating_activity"),
        "cfo_prior": raw_parsed.get("cash_from_operating_activity_prior"),
        "borrowings": raw_parsed.get("borrowings") or raw_parsed.get("total_debt"),
        "other_liabilities": raw_parsed.get("other_liabilities"),
        "market_cap": raw_parsed.get("market_cap"),
        "current_price": raw_parsed.get("current_price"),
        "roce": raw_parsed.get("roce"),
        "debtor_days": raw_parsed.get("debtor_days"),
        "inventory_days": raw_parsed.get("inventory_days"),
        "days_payable": raw_parsed.get("days_payable"),
        "working_capital_days": raw_parsed.get("working_capital_days"),
    }

    for k, v in mappings.items():
        if v is not None:
            data[k] = v

    for k, v in raw_parsed.items():
        if k not in data and v is not None:
            data[k] = v

    return data
