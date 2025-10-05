# run_parser.py
import argparse
from parser_registry import PARSER_REGISTRY

def main():
    parser = argparse.ArgumentParser(description="Bank Statement Parser CLI")
    parser.add_argument("--bank", required=True, help="Bank name (e.g., icici, hdfc, sbi)")
    parser.add_argument("--input", required=True, help="Path to input PDF")
    parser.add_argument("--output", help="Optional path to save CSV output")

    args = parser.parse_args()

    if args.bank not in PARSER_REGISTRY:
        raise ValueError(f"Unsupported bank: {args.bank}. Available: {list(PARSER_REGISTRY.keys())}")

    parse_func = PARSER_REGISTRY[args.bank]
    df = parse_func(args.input)

    if args.output:
        df.to_csv(args.output, index=False)
        print(f"Parsed statement saved to {args.output}")
    else:
        print("Parsed DataFrame preview:")
        print(df.head())

if __name__ == "__main__":
    main()
