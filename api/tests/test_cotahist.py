"""Leitor COTAHIST contra uma linha montada pelas posições do layout oficial da B3."""

from datetime import date

import pytest

from ft.research.cotahist import FIELDS, parse_line


def build_line(**values: str) -> str:
    line = [" "] * 245
    defaults = {
        "tipreg": "01",
        "date": "20150102",
        "codbdi": "02",
        "codneg": "PETR4",
        "tpmerc": "010",
        "nomres": "PETROBRAS",
        "especi": "PN",
        "preabe": "999",
        "premax": "999",
        "premin": "936",
        "premed": "957",
        "preult": "936",
        "totneg": "12345",
        "quatot": "48837200",
        "voltot": "46754792500",
        "fatcot": "1",
        "codisi": "BRPETRACNPR6",
    }
    defaults.update(values)
    numeric = {
        "preabe",
        "premax",
        "premin",
        "premed",
        "preult",
        "totneg",
        "quatot",
        "voltot",
        "fatcot",
        "tipreg",
        "date",
        "tpmerc",
    }
    for name, a, b in FIELDS:
        width = b - a + 1
        v = defaults[name]
        v = v.rjust(width, "0") if name in numeric else v.ljust(width)
        line[a - 1 : b] = list(v[:width])
    return "".join(line)


def test_parses_official_positions():
    row = parse_line(build_line())
    assert row["date"] == date(2015, 1, 2)
    assert row["ticker"] == "PETR4"
    assert row["isin"] == "BRPETRACNPR6"
    assert row["open"] == pytest.approx(9.99)
    assert row["close"] == pytest.approx(9.36)
    assert row["volume"] == 48837200
    assert row["fin_volume"] == pytest.approx(467547925.0)


def test_price_divided_by_quotation_factor():
    row = parse_line(build_line(preult="936000", fatcot="1000"))
    assert row["close"] == pytest.approx(9.36)  # cotação por lote de mil ações


@pytest.mark.parametrize(
    "override",
    [
        {"tpmerc": "020"},  # fracionário
        {"tpmerc": "070"},  # opções
        {"codbdi": "12"},  # fundo imobiliário
        {"codbdi": "14"},  # ETF / certificados
        {"especi": "DIR PN"},  # direito de subscrição
        {"tipreg": "00"},  # cabeçalho
    ],
)
def test_filters_non_equity_records(override):
    assert parse_line(build_line(**override)) is None


def test_keeps_companies_in_judicial_recovery():
    row = parse_line(build_line(codbdi="08", codneg="OGXP3", especi="ON NM"))
    assert row is not None and row["codbdi"] == "08"


def test_rejects_short_lines():
    assert parse_line("01" + " " * 100) is None
