import pandas as pd
from pandas.testing import assert_frame_equal
from custom_parsers.icici_parser import parse


def test_icici_parse_equals_expected():
    expected = pd.read_csv("data/icici/expected.csv")
    out = parse("data/icici/icici sample.pdf")
    assert_frame_equal(out, expected, check_dtype=True, check_like=False)
