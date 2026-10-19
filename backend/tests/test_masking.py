from datetime import date

from backend.platform import masking


def test_strategies():
    assert masking.initials("Ana Ruiz") == "A. R."
    assert masking.initials("maría josé de la cruz") == "M. J. D. L. C."
    assert masking.initials(None) is None
    assert masking.last4("AB1234567") == "\u2022\u2022\u2022\u20224567"
    assert masking.last4("123") == "\u2022\u2022\u2022\u2022"
    assert masking.city_only("12 Elm Street, Austin") == "Austin"
    assert masking.city_only("Austin") == "Austin"
    assert masking.day_only("1987-04-12") == "\u2022\u2022\u2022\u2022-\u2022\u2022-12"
    assert masking.day_only(date(2001, 7, 7)) == "\u2022\u2022\u2022\u2022-\u2022\u2022-07"
    assert masking.day_only("not a date") == "\u2022\u2022\u2022\u2022"
