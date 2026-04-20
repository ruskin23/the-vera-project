from __future__ import annotations

import pytest

from vera.core import timebudget


class TestParseDuration:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("2h", 7200),
            ("30m", 1800),
            ("45s", 45),
            ("1d", 86400),
            ("1D", 86400),
            (" 3h ", 10800),
            ("120", 120),
            (3600, 3600),
            (None, None),
            ("unbounded", None),
            ("none", None),
            ("null", None),
            ("", None),
        ],
    )
    def test_valid(self, value, expected) -> None:
        assert timebudget.parse_duration(value) == expected

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            timebudget.parse_duration("weird")


class TestFormat:
    @pytest.mark.parametrize(
        "seconds,expected",
        [
            (0, "0m"),
            (60, "1m"),
            (3600, "1h"),
            (3660, "1h 1m"),
            (6420, "1h 47m"),
        ],
    )
    def test_format_elapsed(self, seconds, expected) -> None:
        assert timebudget.format_elapsed(seconds) == expected

    def test_format_duration_unbounded(self) -> None:
        assert timebudget.format_duration(None) == "unbounded"
