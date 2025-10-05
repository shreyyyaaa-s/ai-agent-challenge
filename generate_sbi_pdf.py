from pathlib import Path
import pandas as pd
from fpdf import FPDF
import datetime

def generate_fake_sbi_pdf(output_path: str = "data/sbi/sbi_sample.pdf"):
    """
    Generates a fake SBI bank statement PDF with some dummy transaction data.
    """
    df = pd.DataFrame({
        'Date': [
            (datetime.date.today() - datetime.timedelta(days=30)).strftime("%d/%m/%Y"),
            (datetime.date.today() - datetime.timedelta(days=25)).strftime("%d/%m/%Y"),
            (datetime.date.today() - datetime.timedelta(days=20)).strftime("%d/%m/%Y"),
            (datetime.date.today() - datetime.timedelta(days=15)).strftime("%d/%m/%Y"),
            (datetime.date.today() - datetime.timedelta(days=10)).strftime("%d/%m/%Y"),
        ],
        'Description': [
            'Opening Balance',
            'DEPOSIT-ATM 123456789',
            'ONLINE PURCHASE AMAZON',
            'TRANSFER TO JOHN DOE',
            'SALARY CREDIT',
        ],
        'Debit Amt': [
            '',
            '',
            '500.00',
            '1200.00',
            '',
        ],
        'Credit Amt': [
            '10000.00',
            '2500.00',
            '',
            '',
            '35000.00',
        ],
        'Balance': [
            '10000.00',
            '12500.00',
            '12000.00',
            '10800.00',
            '45800.00',
        ]
    })

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "STATE BANK OF INDIA", 0, 1, "C")
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, "Account Statement", 0, 1, "C")
    pdf.ln(10)

    # Account Info
    pdf.set_font("Arial", "B", 10)
    pdf.cell(40, 7, "Account Holder:", 0, 0)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 7, "Mr. A. N. Other", 0, 1)

    pdf.set_font("Arial", "B", 10)
    pdf.cell(40, 7, "Account Number:", 0, 0)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 7, "XXX-XXXXX-1234", 0, 1)
    pdf.ln(5)

    # Table Header
    pdf.set_font("Arial", "B", 8)
    col_widths = [20, 70, 30, 30, 30] # Date, Description, Debit, Credit, Balance
    for i, col in enumerate(df.columns):
        pdf.cell(col_widths[i], 8, str(col), 1, 0, 'C')
    pdf.ln()

    # Table Rows
    pdf.set_font("Arial", "", 8)
    for index, row in df.iterrows():
        for i, col_name in enumerate(df.columns):
            pdf.cell(col_widths[i], 8, str(row[col_name]), 1, 0, 'C')
        pdf.ln()
    
    # Ensure the directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    pdf.output(output_path)
    print(f"Fake SBI PDF generated at: {output_path}")

if __name__ == "__main__":
    generate_fake_sbi_pdf()