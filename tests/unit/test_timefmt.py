import pytest

from lektyra.domain.timefmt import clock, parse_clock, parse_window


def test_clock_strings() -> None:
    assert parse_clock("20:00") == 1_200_000
    assert parse_clock("1:02:03") == 3_723_000
    assert parse_clock("75.5") == 75_500
    assert clock(3_723_000) == "1:02:03"
    assert clock(65_999) == "01:05"


def test_windows() -> None:
    assert parse_window("20:00-30:00") == (1_200_000, 1_800_000)
    with pytest.raises(ValueError):
        parse_window("30:00-20:00")
    with pytest.raises(ValueError):
        parse_clock("twenty")
