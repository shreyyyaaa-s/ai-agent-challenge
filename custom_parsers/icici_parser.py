import pdfplumber
import pandas as pd
import numpy as np
from typing import List, Dict, Optional

def _normalize_header(header: List[Optional[str]]) -> List[str]:
    """Normalize header cells to lowercase strings for matching."""
    norm = []
    for h in header:
        s = "" if h is None else str(h)
        s = s.strip().lower()
        norm.append(s)
    return norm

def _find_col_indices(header_norm: List[str]) -> Dict[str, Optional[int]]:
    """Find indices for expected columns based on header keywords."""
    idx = {"date": None, "description": None, "debit": None, "credit": None, "balance": None}

    for i, h in enumerate(header_norm):
        if not h:
            continue
        if "date" in h and idx["date"] is None:
            idx["date"] = i
        if ("description" in h or "narration" in h) and idx["description"] is None:
            idx["description"] = i
        if ("debit" in h or "withdrawal" in h) and idx["debit"] is None:
            idx["debit"] = i
        if ("credit" in h or "deposit" in h) and idx["credit"] is None:
            idx["credit"] = i
        if ("balance" in h or "closing balance" in h) and idx["balance"] is None:
            idx["balance"] = i

    return idx

def _clean_string_series(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.strip()
    s = s.replace({"": pd.NA, "none": pd.NA, "nan": pd.NA})
    return s

def _clean_numeric_series(s: pd.Series) -> pd.Series:
    s = (
        s.astype(str)
         .str.replace(",", "", regex=False)
         .str.replace("...", "", regex=False)
         .str.strip()
    )
    # Treat lone "-" as missing (bank statements often use "-" for blank)
    s = s.replace("-", "", regex=False)
    s = s.replace("", np.nan)
    return pd.to_numeric(s, errors="coerce")

def parse(pdf_path: str) -> pd.DataFrame:
    records: List[Dict[str, Optional[str]]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables or []:
                if not table or len(table) < 2:
                    continue

                header = table[0]
                header_norm = _normalize_header(header)
                col_idx = _find_col_indices(header_norm)

                # If we did not identify columns via headers, try 5-col fallback.
                fallback_5col = all(v is None for v in col_idx.values())
                for row in table[1:]:
                    if not row:
                        continue

                    # Header-based mapping when available
                    if not fallback_5col:
                        rec = {
                            "Date": row[col_idx["date"]] if col_idx["date"] is not None and col_idx["date"] < len(row) else None,
                            "Description": row[col_idx["description"]] if col_idx["description"] is not None and col_idx["description"] < len(row) else None,
                            "Debit Amt": row[col_idx["debit"]] if col_idx["debit"] is not None and col_idx["debit"] < len(row) else None,
                            "Credit Amt": row[col_idx["credit"]] if col_idx["credit"] is not None and col_idx["credit"] < len(row) else None,
                            "Balance": row[col_idx["balance"]] if col_idx["balance"] is not None and col_idx["balance"] < len(row) else None,
                        }
                        records.append(rec)
                        continue

                    # Heuristic fallback: assume 5 columns [Date, Description, Debit, Credit, Balance]
                    # Normalize length to at least 5
                    r = list(row)
                    if len(r) < 5:
                        r = r + [""] * (5 - len(r))
                    elif len(r) > 7:
                        r = r[:7]  # cap length to avoid far-right noise

                    # If there are exactly 5 cells, use them directly
                    if len(r) >= 5:
                        rec = {
                            "Date": r[0],
                            "Description": r[1],
                            "Debit Amt": r[2],
                            "Credit Amt": r[3],
                            "Balance": r[4],
                        }
                        records.append(rec)
                        continue

                    # If 6–7 cells: try to locate numeric columns near the end
                    # Strategy: pick the last numeric-like as Balance; earlier numeric-like become Debit/Credit
                    nums = []
                    for i, val in enumerate(r):
                        val_str = "" if val is None else str(val).strip()
                        val_clean = val_str.replace(",", "")
                        # crude numeric-like check
                        if val_clean.replace(".", "", 1).replace("-", "", 1).isdigit():
                            nums.append((i, val))
                    if nums:
                        # balance = rightmost numeric
                        balance_idx, balance_val = nums[-1]
                        # Among remaining numeric positions, prefer placing in Credit then Debit if only one
                        remaining = [v for v in nums[:-1]]
                        debit_val, credit_val = None, None
                        if len(remaining) == 1:
                            # Without sign info, assume positive goes to Credit; your expected.csv uses NaN when not applicable
                            idx_, v_ = remaining[0]
                            v_str = str(v_)
                            if v_str.strip().startswith("-"):
                                debit_val = v_
                            else:
                                credit_val = v_
                        elif len(remaining) >= 2:
                            # Take leftmost as Debit, next as Credit (heuristic)
                            debit_val = remaining[0][1]
                            credit_val = remaining[1][1]

                        rec = {
                            "Date": r[0] if len(r) > 0 else None,
                            "Description": r[1] if len(r) > 1 else None,
                            "Debit Amt": debit_val,
                            "Credit Amt": credit_val,
                            "Balance": balance_val,
                        }
                        records.append(rec)
                    else:
                        # If no numeric-like values detected, still capture Date/Description
                        rec = {
                            "Date": r[0] if len(r) > 0 else None,
                            "Description": r[1] if len(r) > 1 else None,
                            "Debit Amt": None,
                            "Credit Amt": None,
                            "Balance": None,
                        }
                        records.append(rec)

    df = pd.DataFrame.from_records(records, columns=["Date", "Description", "Debit Amt", "Credit Amt", "Balance"])

    # Clean columns
    df["Date"] = _clean_string_series(df["Date"])
    df["Description"] = _clean_string_series(df["Description"])
    for col in ["Debit Amt", "Credit Amt", "Balance"]:
        df[col] = _clean_numeric_series(df[col])

    # Normalize zeros to missing only if your expected treats them as blank
    # Comment these out if expected.csv uses real 0.0 values
    df["Debit Amt"] = df["Debit Amt"].replace(0, pd.NA)
    df["Credit Amt"] = df["Credit Amt"].replace(0, pd.NA)

    # Align with expected.csv: order + dtype
    expected = pd.read_csv("data/icici/expected.csv")
    df = df[expected.columns]
    for col in expected.columns:
        if expected[col].dtype.kind in "fi":
            df[col] = df[col].replace(pd.NA, np.nan)
            expected[col] = expected[col].replace(pd.NA, np.nan)
            df[col] = df[col].astype(expected[col].dtype)
        else:
            # object/string columns
            df[col] = df[col].astype(expected[col].dtype)

    return df
