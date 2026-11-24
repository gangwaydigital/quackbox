"""Tests for normalized quote verification."""
from app.services.case_quotes import verify_quote


def test_whitespace_and_case():
    assert verify_quote("the  Deal is\nOFF", "Hi. The deal is off, sorry.")


def test_smart_quotes_and_dashes():
    assert verify_quote("“yes” – fine", '"yes" - fine')


def test_reply_markers():
    assert verify_quote("we agreed to pay", "> we agreed\n> to pay")


def test_invented_quote_fails():
    assert not verify_quote("we never agreed", "we agreed to pay")


def test_null_body():
    assert not verify_quote("anything", None)


def test_empty_quote_fails():
    assert not verify_quote("   ", "body")
