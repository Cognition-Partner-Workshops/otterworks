import pytest

from parity.connection import validate_date


@pytest.mark.parametrize('value', ['20261109', '20240229', '19991231'])
def test_valid_calendar_date(value):
    assert validate_date(value) == value


@pytest.mark.parametrize('value', ["20261109'); DELETE FROM x; --", '2026119',
                                 '20260229', '20261301', '２０２６１１０９'])
def test_invalid_date_rejected(value):
    with pytest.raises(ValueError):
        validate_date(value)
