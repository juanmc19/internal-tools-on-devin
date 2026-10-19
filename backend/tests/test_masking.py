from datetime import date

import pytest

from backend.platform import masking


def test_strategies():
    assert masking.initials("Ana Ruiz") == "A. R."
    assert masking.initials("maría josé de la cruz") == "M. J. D. L. C."
    assert masking.initials(None) is None
    assert masking.last4("AB1234567") == "\u2022\u2022\u2022\u20224567"
    assert masking.last4("123") == "\u2022\u2022\u2022\u2022"
    assert masking.day_only("1987-04-12") == "\u2022\u2022\u2022\u2022-\u2022\u2022-12"
    assert masking.day_only(date(2001, 7, 7)) == "\u2022\u2022\u2022\u2022-\u2022\u2022-07"
    assert masking.day_only("not a date") == "\u2022\u2022\u2022\u2022"


@pytest.mark.parametrize(
    "address",
    ["12 Elm St, Apt 4", "12 Elm St, Rear", "12 Elm St, Penthouse", "12 Elm Street, Austin", "Austin", ""],
)
def test_redact_masks_the_whole_address_whatever_its_last_part(address):
    assert masking.redact(address) == "\u2022\u2022\u2022\u2022"
    assert masking.apply("redact", address) == "\u2022\u2022\u2022\u2022"


def test_redact_keeps_none_and_city_only_is_gone():
    assert masking.redact(None) is None
    assert "city_only" not in masking.STRATEGIES
    with pytest.raises(ValueError):
        masking.apply("city_only", "12 Elm St, Austin")
