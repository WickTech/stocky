"""Universe config sanity (no network)."""

import market_intelligence as mi


def test_global_universe_spans_several_markets_and_has_no_duplicates():
    tickers = mi.GLOBAL_STOCKS
    assert len(tickers) == len(set(tickers))
    suffixes = {t.rsplit(".", 1)[1] if "." in t else "US" for t in tickers}
    assert len(suffixes) >= 4  # US plus several exchanges


def test_universes_do_not_overlap():
    groups = [mi.INDIAN_STOCKS, mi.GLOBAL_STOCKS, mi.FOREX_PAIRS]
    flat = [t for g in groups for t in g]
    assert len(flat) == len(set(flat))


def test_outputs_are_distinct_files():
    outs = {mi.EQUITY_OUTPUT, mi.GLOBAL_OUTPUT, mi.FOREX_OUTPUT}
    assert len(outs) == 3
