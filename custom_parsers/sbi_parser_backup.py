import pdfplumber
import pandas as pd

def parse(pdf_path: str) -> pd.DataFrame:
    rows = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if not table:
                continue

            for row in table:
                # Skip headers or malformed rows
                if row[0] == "Date" or len(row) < 5:
                    continue

                rows.append({
                    "Date": row[0].strip(),
                    "Description": row[1].strip(),
                    "Debit Amt": row[2].strip() if row[2] else "",
                    "Credit Amt": row[3].strip() if row[3] else "",
                    "Balance": row[4].strip() if row[4] else "",
                })

    df = pd.DataFrame(rows)

    # Clean up types
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)
    df["Debit Amt"] = pd.to_numeric(df["Debit Amt"].str.replace(",", ""), errors="coerce")
    df["Credit Amt"] = pd.to_numeric(df["Credit Amt"].str.replace(",", ""), errors="coerce")
    df["Balance"] = pd.to_numeric(df["Balance"].str.replace(",", ""), errors="coerce")

    return df
