import pytest

from GalenLibrary.bridge import LayoutMessage, LayoutResult
from GalenLibrary.library import LayoutValidationError


def last_spec(lib) -> str:
    return lib._bridge.specs[-1]


def test_below_generates_spec(make_library):
    lib = make_library()
    lib.element_should_be_below("id:menu", "id:header", "0")
    assert last_spec(lib) == (
        "@objects\n"
        "    menu    id    menu\n"
        "    header    id    header\n"
        "\n"
        "= Check =\n"
        "    menu:\n"
        "        below header 0px\n"
    )
    _, call = lib._bridge.calls[-1]
    assert call["report_only_on_failure"] is True


@pytest.mark.parametrize(
    "keyword, args, expected",
    [
        ("element_should_be_above", ("id:a", "id:b"), "above b"),
        ("element_should_be_left_of", ("id:a", "id:b", "10 to 20px"), "left-of b 10 to 20px"),
        ("element_should_be_right_of", ("id:a", "id:b", "~ 5px"), "right-of b ~ 5px"),
        ("element_should_be_inside", ("id:a", "id:b", "16px left"), "inside b 16px left"),
        ("element_should_be_inside", ("id:a", "screen"), "inside screen"),
        ("element_should_be_near", ("id:a", "id:b", "10px left"), "near b 10px left"),
        ("element_should_be_centered", ("id:a", "viewport"), "centered all inside viewport"),
        ("element_width_should_be", ("id:a", "120"), "width 120px"),
        (
            "element_height_should_be",
            ("id:a", "50% of viewport/height"),
            "height 50% of viewport/height",
        ),
        (
            "element_css_property_should_be",
            ("id:a", "font-size", "18px"),
            'css font-size is "18px"',
        ),
        ("element_color_scheme_should_be", ("id:a", "> 60% white"), "color-scheme > 60% white"),
    ],
)
def test_spec_lines(make_library, keyword, args, expected):
    lib = make_library()
    getattr(lib, keyword)(*args)
    assert f"        {expected}\n" in last_spec(lib)


def test_inside_partly_and_centered_tolerance(make_library):
    lib = make_library()
    lib.element_should_be_inside("id:a", "viewport", partly=True)
    assert "inside partly viewport" in last_spec(lib)
    lib.element_should_be_centered("id:a", "id:b", direction="Vertically", tolerance=5)
    assert "centered vertically inside b 5px" in last_spec(lib)


def test_aligned_with_one_locator_checks_all_matches(make_library):
    lib = make_library()
    lib.elements_should_be_aligned("css:.card", edge="top", tolerance=2)
    spec = last_spec(lib)
    assert "    card-*    css    .card\n" in spec
    assert "@forEach [card-*] as item, next as nextItem" in spec
    assert "aligned horizontally top ${nextItem} 2px" in spec


def test_aligned_with_several_locators_chains_them(make_library):
    lib = make_library()
    lib.elements_should_be_aligned("id:a", "id:b", "id:c", direction="vertically", edge="left")
    spec = last_spec(lib)
    assert "    a:\n        aligned vertically left b\n" in spec
    assert "    b:\n        aligned vertically left c\n" in spec


@pytest.mark.parametrize(
    "kwargs", [{"direction": "diagonal"}, {"direction": "vertically", "edge": "top"}]
)
def test_aligned_rejects_bad_arguments(make_library, kwargs):
    with pytest.raises(ValueError):
        make_library().elements_should_be_aligned("css:.card", **kwargs)


def test_raw_spec_with_named_references(make_library):
    lib = make_library()
    lib.element_should_satisfy_spec(
        "id:logo", "inside hdr 16px left", "width 120px", hdr="id:header"
    )
    spec = last_spec(lib)
    assert "    hdr    id    header\n" in spec
    assert "    logo:\n        inside hdr 16px left\n        width 120px\n" in spec


def test_failure_message_is_galen_message(make_library):
    lib = make_library()
    lib._bridge.layout_result = LayoutResult(
        1, 0, [LayoutMessage('"menu" is 5px below "header" instead of 0px', "check-1.gspec:7")]
    )
    with pytest.raises(LayoutValidationError) as error:
        lib.element_should_be_below("id:menu", "id:header", "0px")
    assert str(error.value) == '"menu" is 5px below "header" instead of 0px'


def test_css_value_is_quoted(make_library):
    lib = make_library()
    lib.element_css_property_should_be("id:a", "font-family", 'Segoe "UI"', match="contains")
    assert 'css font-family contains "Segoe \\"UI\\""' in last_spec(lib)
