import pytest

from GalenLibrary.locators import object_name, to_galen


@pytest.mark.parametrize(
    "locator, expected",
    [
        ("id:logo", ("id", "logo")),
        ("id=logo", ("id", "logo")),
        ("css:#menu a", ("css", "#menu a")),
        ("css=.card", ("css", ".card")),
        ("xpath://div[@id='x']", ("xpath", "//div[@id='x']")),
        ("//div[@id='x']", ("xpath", "//div[@id='x']")),
        ("(//div)[2]", ("xpath", "(//div)[2]")),
        ("class:card big", ("css", ".card.big")),
        ("tag:h1", ("css", "h1")),
        ("name:q", ("xpath", '//*[@name="q"]')),
        ("link:Contact us", ("xpath", '//a[normalize-space(.)="Contact us"]')),
        ("partial link:Cont", ("xpath", '//a[contains(normalize-space(.), "Cont")]')),
        ("logo", ("xpath", '//*[@id="logo" or @name="logo"]')),
        ("screen", ("screen", "screen")),
        ("viewport", ("viewport", "viewport")),
    ],
)
def test_to_galen(locator, expected):
    assert to_galen(locator) == expected


def test_quotes_in_values():
    assert to_galen("name:it's") == ("xpath", '//*[@name="it\'s"]')
    assert to_galen('name:say "hi"') == ("xpath", "//*[@name='say \"hi\"']")


@pytest.mark.parametrize("locator", ["dom:document.body", "jquery:div", ""])
def test_unsupported(locator):
    with pytest.raises(ValueError):
        to_galen(locator)


def test_object_names_are_readable_and_unique():
    taken = set()
    assert object_name("id:logo", taken) == "logo"
    assert object_name("css:#logo", taken) == "logo-2"
    assert object_name("css:#products .card", taken) == "products-card"
    assert object_name("xpath://div[@id='hero']", taken) == "hero"
    assert object_name("//section/div", taken) == "element"
    assert object_name("id:screen", taken) == "screen-element"
    assert object_name("css:.1col", taken) == "el-1col"
