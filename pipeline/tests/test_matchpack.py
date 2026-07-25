"""Unit tests for match-pack URL/argument logic (no browser, no network)."""

import pytest
from pipeline.matchpack import parse_comp, report_url


def test_parse_comp() -> None:
    assert parse_comp("43-106") == (43, 106)
    assert parse_comp("55-282") == (55, 282)
    with pytest.raises(ValueError):
        parse_comp("euro24")
    with pytest.raises(ValueError):
        parse_comp("43/106")


def test_report_url_encodes_tab_and_scope() -> None:
    url = report_url("http://localhost:8000", "55-282", 772)
    assert url == "http://localhost:8000/?comp=55-282&team=772&tab=Match%20report"
