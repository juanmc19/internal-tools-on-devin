from datetime import date

import pytest

from backend.platform import masking


def test_strategies():
    assert masking.initials("Ana Ruiz") == "A. R."
    assert masking.initials("maría josé de la cruz") == "M. J. D. L. C."
    assert masking.initials(None) is None
    assert masking.last4("AB1234567") == "\u2022\u2022\u2022\u20224567"
    assert masking.last4("123") == "\u2022\u2022\u2022\u2022"
    assert masking.city_only("12 Elm Street, Austin") == "Austin"
    assert masking.city_only("Austin") == "\u2022\u2022\u2022\u2022"
    assert masking.city_only("12 Elm Street Austin") == "\u2022\u2022\u2022\u2022"
    assert masking.city_only("12 Elm Street, ") == "\u2022\u2022\u2022\u2022"
    assert masking.city_only(None) is None
    assert masking.day_only("1987-04-12") == "\u2022\u2022\u2022\u2022-\u2022\u2022-12"
    assert masking.day_only(date(2001, 7, 7)) == "\u2022\u2022\u2022\u2022-\u2022\u2022-07"
    assert masking.day_only("not a date") == "\u2022\u2022\u2022\u2022"


@pytest.mark.parametrize(
    "address",
    [
        "12 Elm St, Apt 4",
        "12 Elm St, Apt. B",
        "Calle Sol 12, Depto 3B",
        "Av. Reforma 222, Suite B",
        "Rua das Flores 5, Bloco C",
        "12 Elm St, #4",
        "12 Elm St, 4B",
        "12 Elm St, Austin 78701",
    ],
)
def test_city_only_masks_a_last_component_that_is_not_a_city(address):
    assert masking.city_only(address) == "\u2022\u2022\u2022\u2022"


@pytest.mark.parametrize(
    "city", ["Ciudad de México", "São Paulo", "Bogotá", "Valparaíso", "Rio de Janeiro", "St. John's"]
)
def test_city_only_keeps_a_real_city(city):
    assert masking.city_only(f"221 Av. Libertador, {city}") == city
