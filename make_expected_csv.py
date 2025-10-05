import pandas as pd
from pathlib import Path

df = pd.DataFrame([
    {"Date":"2025-09-05","Description":"Opening Balance","Debit Amt":0.0,"Credit Amt":10000.0,"Balance":10000.0},
    {"Date":"2025-09-10","Description":"DEPOSIT-ATM 123456789","Debit Amt":0.0,"Credit Amt":2500.0,"Balance":12500.0},
    {"Date":"2025-09-15","Description":"ONLINE PURCHASE AMAZON","Debit Amt":500.0,"Credit Amt":0.0,"Balance":12000.0},
    {"Date":"2025-09-20","Description":"TRANSFER TO JOHN DOE","Debit Amt":1200.0,"Credit Amt":0.0,"Balance":10800.0},
    {"Date":"2025-09-25","Description":"SALARY CREDIT","Debit Amt":0.0,"Credit Amt":35000.0,"Balance":45800.0},
])

Path("data/sbi").mkdir(parents=True, exist_ok=True)
df.to_csv("data/sbi/sbi_sample.csv", index=False)
print("Expected CSV written to data/sbi/sbi_sample.csv")
