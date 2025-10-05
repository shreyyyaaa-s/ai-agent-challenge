import pdfplumber
import pandas as pd
import re
import numpy as np

def parse(pdf_path: str) -> pd.DataFrame:
    """
    Extracts transaction data from SBI bank statements in PDF format.

    Args:
        pdf_path (str): The path to the PDF bank statement.

    Returns:
        pd.DataFrame: A DataFrame with columns 'Date', 'Description',
                      'Debit Amt', 'Credit Amt', 'Balance'.
                      Returns an empty DataFrame if no transactions are found or
                      the PDF cannot be parsed.
    """
    all_transactions_data = []

    # Define robust column keyword mappings for common SBI statement variations.
    # Keys are our target DataFrame column names.
    # Values are lists of possible text fragments found in PDF headers (case-insensitive).
    column_keyword_map = {
        'Date': ['date', 'txn date', 'transaction date'],
        'Description': ['description', 'particulars', 'particular'],
        'Debit Amt': ['debit', 'withdrawal', 'amount (dr)', 'amt.dr', 'amountdr'],
        'Credit Amt': ['credit', 'deposit', 'amount (cr)', 'amt.cr', 'amountcr'],
        'Balance': ['balance', 'closing balance', 'cl bal', 'closingbal', 'available balance']
    }
    target_columns = ['Date', 'Description', 'Debit Amt', 'Credit Amt', 'Balance']

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                # Extract tables. Default settings are often a good start for SBI statements.
                # Custom settings can be added here if default table extraction is not robust.
                # Example: table_settings = {"vertical_strategy": "lines", "horizontal_strategy": "lines", "snap_tolerance": 3}
                tables = page.extract_tables()

                for table_data in tables:
                    if not table_data:
                        continue

                    current_page_column_mapping = {}
                    header_row_index = -1

                    # Attempt to find the header row within the current table_data
                    for r_idx, row in enumerate(table_data):
                        # Clean and normalize row cells for robust matching
                        # Convert to string, lowercase, strip whitespace, replace newlines with space
                        clean_row = [str(cell).lower().strip().replace('\n', ' ') if cell is not None else '' for cell in row]

                        temp_mapping = {}
                        found_keys_count = 0
                        
                        # Iterate through target columns and their keywords to find a match in the clean_row
                        for col_name, keywords in column_keyword_map.items():
                            for keyword in keywords:
                                for c_idx, cell_content in enumerate(clean_row):
                                    if keyword in cell_content:
                                        # Map the column index to our standard column name.
                                        # Ensure no duplicate mapping for the same column index from different keywords.
                                        if c_idx not in temp_mapping:
                                            temp_mapping[c_idx] = col_name
                                            found_keys_count += 1
                                            break # Found a keyword for this column, move to the next target_col
                                # If a mapping for the current `col_name` was established, break from keywords loop
                                if c_idx in temp_mapping and temp_mapping[c_idx] == col_name:
                                    break

                        # A row is considered a header if it contains 'Date' and at least 3 other key columns
                        # (e.g., Description, Debit/Credit, Balance), or if 'Description' and 'Balance' are present.
                        # This heuristic can be fine-tuned based on specific SBI statement layouts.
                        is_likely_header = ('Date' in temp_mapping.values() and found_keys_count >= 3) or \
                                           ('Date' in temp_mapping.values() and 'Description' in temp_mapping.values() and 'Balance' in temp_mapping.values())

                        if is_likely_header:
                            current_page_column_mapping = temp_mapping
                            header_row_index = r_idx
                            break # Found the header for this table, stop searching for headers

                    if not current_page_column_mapping:
                        # No valid header found for this table, likely not a transaction table, so skip.
                        continue

                    # Extract data rows from the table, skipping the identified header row
                    data_rows = table_data[header_row_index + 1:]

                    for row in data_rows:
                        transaction = {}
                        # Only process cells that correspond to our identified columns
                        for col_idx, value in enumerate(row):
                            if col_idx in current_page_column_mapping:
                                col_name = current_page_column_mapping[col_idx]
                                transaction[col_name] = value

                        # Basic check to filter out empty or non-transaction-like rows.
                        # A row must have a Date and at least one other significant field (Description or an Amount).
                        if transaction.get('Date') and (
                            transaction.get('Description') or
                            transaction.get('Debit Amt') or
                            transaction.get('Credit Amt') or
                            transaction.get('Balance')
                        ):
                            # Filter out rows that might be sub-headers or footers if they got pulled
                            # e.g., rows with 'Total' or 'Page' without actual transaction data
                            description_str = str(transaction.get('Description', '')).lower()
                            if not any(kw in description_str for kw in ['total', 'page', 'balance brought forward', 'balance carried forward']):
                                all_transactions_data.append(transaction)

    except Exception as e:
        print(f"Error processing PDF '{pdf_path}': {e}")
        return pd.DataFrame(columns=target_columns) # Return empty DataFrame on error

    if not all_transactions_data:
        return pd.DataFrame(columns=target_columns)

    df = pd.DataFrame(all_transactions_data)

    # Ensure all target columns exist, filling missing ones with NaN
    for col in target_columns:
        if col not in df.columns:
            df[col] = np.nan
    df = df[target_columns].copy() # Ensure specific column order and prevent SettingWithCopyWarning

    # Data Cleaning and Type Conversion
    # 1. Numeric Columns: Remove non-numeric characters (except decimal point and sign), convert to float
    numeric_cols = ['Debit Amt', 'Credit Amt', 'Balance']
    for col in numeric_cols:
        if col in df.columns:
            # Convert to string first to handle potential mixed types and apply string operations
            df[col] = df[col].astype(str)
            # Remove all non-numeric characters except digits, '.', and '-'
            df[col] = df[col].str.replace(r'[^\d.-]', '', regex=True)
            # Replace empty strings (e.g., from cells containing only '-' or spaces after cleanup) with NaN
            df[col] = df[col].replace('', np.nan)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0) # Convert to float, fill unparsable with 0.0

    # 2. Date Column: Convert to datetime
    if 'Date' in df.columns:
        # Assuming common SBI date formats like DD-MM-YYYY or DD/MM/YYYY
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce', dayfirst=True)
        # Drop rows where Date could not be parsed (likely non-transaction data picked up)
        df.dropna(subset=['Date'], inplace=True)
        df['Date'] = df['Date'].dt.normalize() # Remove time component for cleaner dates

    # 3. Description Column: Clean up whitespace and potential extra text/artifacts
    if 'Description' in df.columns:
        df['Description'] = df['Description'].astype(str).str.strip()
        # Remove common page number artifacts that might get concatenated by pdfplumber
        df['Description'] = df['Description'].apply(lambda x: re.sub(r'\s*\(?Page\s*\d+\s*of\s*\d+\)?\s*', '', x, flags=re.IGNORECASE))
        # Replace string 'nan' with an empty string, which can occur after `astype(str)` for actual NaNs
        df['Description'] = df['Description'].replace('nan', '')

    # Final filtering: Remove rows that might be partial or junk after cleaning.
    # For instance, rows with a valid date but empty description and all zero amounts are suspicious.
    df = df[~((df['Description'] == '') & (df['Debit Amt'] == 0) & (df['Credit Amt'] == 0) & (df['Balance'] == 0))].copy()

    # Drop rows that ended up with all NaNs after initial processing (unlikely with current approach, but a good safeguard)
    df.dropna(how='all', inplace=True)

    return df.reset_index(drop=True)