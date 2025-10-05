from dotenv import load_dotenv
load_dotenv()  # take environment variables from .env.

# agent.py
import argparse
import pandas as pd
from pandas.testing import assert_frame_equal
from parser_registry import PARSER_REGISTRY

from typing import TypedDict, Optional
from pathlib import Path
from langgraph.graph import StateGraph, END
import os
import importlib.util

# Use the correct SDK
from google import genai

# --- Define the agent state schema ---
class AgentState(TypedDict, total=False):
    target: str
    input: str
    expected: Optional[str]
    attempt: int
    df: Optional[pd.DataFrame]
    success: Optional[bool]

# --- Helper: dynamic import ---
def load_parser(target: str, parser_path: Path):
    spec = importlib.util.spec_from_file_location(f"{target}_parser", parser_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse

# --- Define nodes ---
def plan_node(state: AgentState) -> AgentState:
    target = state["target"]
    print(f" Plan: Parse {target} statement")
    return state

def generate_parser_node(state: AgentState) -> AgentState:
    target = state["target"]
    parser_path = Path(f"custom_parsers/{target}_parser.py")

    # If parser already exists, just load and register it
    if parser_path.exists():
        print(f" Parser for {target} already exists, skipping generation")
        if target not in PARSER_REGISTRY:
            PARSER_REGISTRY[target] = load_parser(target, parser_path)
        return state

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print(" No GOOGLE_API_KEY found. Writing stub parser instead.")
        parser_path.write_text(
            "import pandas as pd\n\n"
            "def parse(pdf_path: str) -> pd.DataFrame:\n"
            f"    # TODO: implement parsing logic for {target}\n"
            "    return pd.DataFrame(columns=['Date','Description','Debit Amt','Credit Amt','Balance'])\n",
            encoding="utf-8"
        )
        PARSER_REGISTRY[target] = load_parser(target, parser_path)
        return state

    try:
        print(f"Generating new parser for {target} using Gemini...")

        client = genai.Client(api_key=api_key)

        prompt = f"""
        Write a Python function `parse(pdf_path: str) -> pd.DataFrame` that extracts
        transactions from {target} bank statements in PDF format.

        The DataFrame must have columns:
        - Date
        - Description
        - Debit Amt
        - Credit Amt
        - Balance

        Use pdfplumber for PDF parsing. Ensure robust handling of headers, merged cells,
        and numeric cleanup (remove commas, coerce to float).
        """

        response = client.models.generate_content(
            model="models/gemini-2.5-flash",
            contents=prompt
        )
        code = response.text

        # Clean Gemini output (remove markdown fences, language tags)
        if "```" in code:
            parts = code.split("```")
            code = max(parts, key=len)
            code = code.replace("python", "").strip()

        # Sanity check: ensure code is valid Python
        try:
            compile(code, "<string>", "exec")
        except SyntaxError as e:
            raise RuntimeError(f"Generated code invalid: {e}")

        parser_path.write_text(code, encoding="utf-8")
        print(f" Wrote new parser: {parser_path}")

        # Try to load and register the parser
        PARSER_REGISTRY[target] = load_parser(target, parser_path)

    except Exception as e:
        print(f" Gemini call failed: {e}")
        print(" Writing stub parser instead.")
        parser_path.write_text(
            "import pandas as pd\n\n"
            "def parse(pdf_path: str) -> pd.DataFrame:\n"
            f"    # TODO: implement parsing logic for {target}\n"
            "    return pd.DataFrame(columns=['Date','Description','Debit Amt','Credit Amt','Balance'])\n",
            encoding="utf-8"
        )
        PARSER_REGISTRY[target] = load_parser(target, parser_path)

    return state

def parse_node(state: AgentState) -> AgentState:
    target = state["target"]
    input_path = state["input"]
    parse_func = PARSER_REGISTRY[target]
    print(f" Running parser for {target} (attempt {state['attempt']})...")
    df = parse_func(input_path)
    return {**state, "df": df}

def test_node(state: AgentState) -> AgentState:
    if not state.get("expected"):
        print(" No expected CSV provided, skipping test")
        print(" Parsed DataFrame preview:")
        print(state["df"].head())
        return {**state, "success": True}

    expected = pd.read_csv(state["expected"])
    df = state["df"]

    try:
        assert_frame_equal(df, expected, check_dtype=False, check_like=True)
        print(" Output matches expected CSV")
        return {**state, "success": True}
    except AssertionError as e:
        attempt = state.get("attempt", 1)
        print(f" Test failed on attempt {attempt}: {e}")
        if attempt >= 3:
            print(" Max attempts reached. Exiting.")
            return {**state, "success": False}
        else:
            return {**state, "attempt": attempt + 1, "success": False}

# --- Build the graph ---
workflow = StateGraph(AgentState)
workflow.add_node("plan", plan_node)
workflow.add_node("generate_parser", generate_parser_node)
workflow.add_node("parse", parse_node)
workflow.add_node("test", test_node)

workflow.set_entry_point("plan")
workflow.add_edge("plan", "generate_parser")
workflow.add_edge("generate_parser", "parse")
workflow.add_edge("parse", "test")

workflow.add_conditional_edges(
    "test",
    lambda state: "retry" if not state.get("success") and state.get("attempt", 1) <= 3 else "end",
    {
        "retry": "parse",
        "end": END,
    },
)

app = workflow.compile()

# --- CLI Entrypoint ---
def main():
    parser = argparse.ArgumentParser(description="LangGraph Agent for Bank Parsers")
    parser.add_argument("--target", required=True, help="Bank target (e.g., icici, sbi)")
    parser.add_argument("--input", required=True, help="Path to input PDF")
    parser.add_argument("--expected", required=False, help="Optional expected CSV for validation")
    args = parser.parse_args()

    init_state: AgentState = {
        "target": args.target,
        "input": args.input,
        "expected": args.expected,
        "attempt": 1,
    }

    final_state = app.invoke(init_state)

    if final_state.get("success"):
        print(" Agent run completed successfully")
    else:
        print(" Agent run ended with failures")

if __name__ == "__main__":
    main()
