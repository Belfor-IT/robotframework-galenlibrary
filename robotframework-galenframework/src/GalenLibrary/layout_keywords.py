"""Galen layout checks as Robot Framework keywords.

Every keyword builds a small Galen spec on the fly and runs it in the browser session of
SeleniumLibrary, so no knowledge of the Galen spec language is needed.
"""

from typing import Optional

from robot.api.deco import keyword

from GalenLibrary.base import GalenContext, px
from GalenLibrary.specs import SpecBuilder

_DIRECTIONS = ("all", "horizontally", "vertically")
_EDGES = {
    "horizontally": ("all", "top", "bottom", "centered"),
    "vertically": ("all", "left", "right", "centered"),
}
_CSS_MATCH = ("is", "contains", "starts", "ends", "matches")


def _quote(text: str) -> str:
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


class LayoutKeywords(GalenContext):
    # --- relative position -------------------------------------------------------

    def _relative(self, relation: str, locator: str, reference: str, distance) -> None:
        spec = SpecBuilder()
        element, ref = spec.element(locator), spec.element(reference)
        check = f"{relation} {ref}" + (f" {px(distance)}" if distance not in (None, "") else "")
        spec.check(element, check)
        self._run_builder(spec, f"{element} {relation} {ref}")

    @keyword
    def element_should_be_above(self, locator: str, reference: str, distance: Optional[str] = None):
        """Verifies that ``locator`` is above ``reference``.

        ``distance`` is the gap between the bottom of the element and the top of the
        reference: ``0px``, ``10`` (= ``10px``), ``10 to 20px``, ``~ 15px``, ``> 5px`` or
        ``< 30px``. Without ``distance`` any gap of 0px or more is accepted.

        | Element Should Be Above    id:menu    id:content    0px
        | Element Should Be Above    css:.logo    id:footer
        """
        self._relative("above", locator, reference, distance)

    @keyword
    def element_should_be_below(self, locator: str, reference: str, distance: Optional[str] = None):
        """Verifies that ``locator`` is below ``reference``. See `Element Should Be Above` for ``distance``.

        | Element Should Be Below    id:menu    id:header    0px
        """
        self._relative("below", locator, reference, distance)

    @keyword
    def element_should_be_left_of(
        self, locator: str, reference: str, distance: Optional[str] = None
    ):
        """Verifies that ``locator`` is left of ``reference``. See `Element Should Be Above` for ``distance``.

        | Element Should Be Left Of    id:logo    id:search    20 to 40px
        """
        self._relative("left-of", locator, reference, distance)

    @keyword
    def element_should_be_right_of(
        self, locator: str, reference: str, distance: Optional[str] = None
    ):
        """Verifies that ``locator`` is right of ``reference``. See `Element Should Be Above` for ``distance``.

        | Element Should Be Right Of    id:search    id:logo
        """
        self._relative("right-of", locator, reference, distance)

    @keyword
    def element_should_be_inside(
        self, locator: str, container: str, offsets: Optional[str] = None, partly: bool = False
    ):
        """Verifies that ``locator`` lies inside ``container``.

        ``offsets`` optionally gives the distance to the container edges, e.g. ``16px left``,
        ``0px top left right`` or ``10 to 20px left, 5px top``. With ``partly=True`` the
        element only has to overlap the container. ``container`` may be ``screen``
        (the whole page) or ``viewport`` (the visible part of the browser window).

        | Element Should Be Inside    id:logo      id:header    16px left
        | Element Should Be Inside    id:header    screen       0px top left right
        | Element Should Be Inside    id:banner    viewport     partly=True
        """
        spec = SpecBuilder()
        element, ref = spec.element(locator), spec.element(container)
        check = "inside " + ("partly " if partly else "") + ref + (f" {offsets}" if offsets else "")
        spec.check(element, check)
        self._run_builder(spec, f"{element} inside {ref}")

    @keyword
    def element_should_be_near(self, locator: str, reference: str, offsets: str):
        """Verifies that ``locator`` is close to ``reference`` at the given sides.

        ``offsets`` is the distance from the reference, e.g. ``10px left`` (the element is
        10px to the left of the reference) or ``5 to 15px top, 0px right``.

        | Element Should Be Near    id:label    id:input    10px left
        """
        spec = SpecBuilder()
        element, ref = spec.element(locator), spec.element(reference)
        spec.check(element, f"near {ref} {offsets}")
        self._run_builder(spec, f"{element} near {ref}")

    @keyword
    def element_should_be_centered(
        self,
        locator: str,
        container: str,
        direction: str = "all",
        tolerance: Optional[str] = None,
    ):
        """Verifies that ``locator`` is centered inside ``container``.

        ``direction`` is ``all`` (default), ``horizontally`` or ``vertically``.
        ``tolerance`` is the allowed deviation in pixels (Galen default ``2px``).

        | Element Should Be Centered    id:logo     id:header    vertically
        | Element Should Be Centered    id:dialog   viewport     tolerance=5
        """
        direction = direction.lower()
        if direction not in _DIRECTIONS:
            raise ValueError(
                f"direction must be one of {', '.join(_DIRECTIONS)}, got '{direction}'."
            )
        spec = SpecBuilder()
        element, ref = spec.element(locator), spec.element(container)
        check = f"centered {direction} inside {ref}"
        if tolerance not in (None, ""):
            check += f" {px(tolerance)}"
        spec.check(element, check)
        self._run_builder(spec, f"{element} centered {direction} in {ref}")

    @keyword
    def elements_should_be_aligned(
        self, *locators: str, direction: str = "horizontally", edge: str = "all", tolerance: int = 0
    ):
        """Verifies that elements are aligned with each other.

        Give one locator that matches several elements (e.g. ``css:.card``) or several
        locators. ``direction=horizontally`` means the elements are in one row, with
        ``edge`` ``all`` (default), ``top``, ``bottom`` or ``centered``.
        ``direction=vertically`` means one column, with ``edge`` ``all``, ``left``,
        ``right`` or ``centered``. ``tolerance`` is the allowed deviation in pixels.

        | Elements Should Be Aligned    css:.card
        | Elements Should Be Aligned    css:.card    direction=vertically    edge=left
        | Elements Should Be Aligned    id:logo    id:menu    id:search    edge=centered    tolerance=2
        """
        direction, edge = direction.lower(), edge.lower()
        if direction not in _EDGES:
            raise ValueError("direction must be 'horizontally' or 'vertically'.")
        if edge not in _EDGES[direction]:
            raise ValueError(
                f"edge for {direction} alignment must be one of {', '.join(_EDGES[direction])}."
            )
        if not locators:
            raise ValueError("At least one locator is required.")
        rate = f" {int(tolerance)}px" if int(tolerance) else ""

        spec = SpecBuilder()
        if len(locators) == 1:
            pattern = spec.elements(locators[0])
            spec.for_each_pair(pattern, f"aligned {direction} {edge} {{next}}{rate}")
            title = f"{pattern} aligned {direction}"
        else:
            names = [spec.element(loc) for loc in locators]
            for current, following in zip(names, names[1:]):
                spec.check(current, f"aligned {direction} {edge} {following}{rate}")
            title = f"{', '.join(names)} aligned {direction}"
        self._run_builder(spec, title)

    # --- size --------------------------------------------------------------------

    @keyword
    def element_width_should_be(self, locator: str, expected: str):
        """Verifies the width of ``locator``.

        ``expected`` can be ``120px`` (or just ``120``), ``100 to 200px``, ``~ 120px``,
        ``> 50px``, ``< 300px`` or relative to the page or window, like
        ``50% of screen/width`` or ``25 to 30% of viewport/width``.

        | Element Width Should Be    id:logo       120px
        | Element Width Should Be    id:sidebar    25 to 30% of viewport/width
        """
        spec = SpecBuilder()
        element = spec.element(locator)
        spec.check(element, f"width {px(expected)}")
        self._run_builder(spec, f"{element} width")

    @keyword
    def element_height_should_be(self, locator: str, expected: str):
        """Verifies the height of ``locator``. See `Element Width Should Be` for ``expected``.

        | Element Height Should Be    id:header    70px
        """
        spec = SpecBuilder()
        element = spec.element(locator)
        spec.check(element, f"height {px(expected)}")
        self._run_builder(spec, f"{element} height")

    # --- look --------------------------------------------------------------------

    @keyword
    def element_css_property_should_be(
        self, locator: str, property: str, expected: str, match: str = "is"
    ):
        """Verifies a computed CSS property of ``locator``.

        ``match`` is ``is`` (default), ``contains``, ``starts``, ``ends`` or ``matches``
        (regular expression). Colours are reported by the browser as ``rgba(...)``.

        | Element Css Property Should Be    id:title    font-size     32px
        | Element Css Property Should Be    id:title    font-family   Segoe    match=contains
        """
        match = match.lower()
        if match not in _CSS_MATCH:
            raise ValueError(f"match must be one of {', '.join(_CSS_MATCH)}.")
        spec = SpecBuilder()
        element = spec.element(locator)
        spec.check(element, f"css {property} {match} {_quote(expected)}")
        self._run_builder(spec, f"{element} css {property}")

    @keyword
    def element_color_scheme_should_be(self, locator: str, scheme: str):
        """Verifies which colours fill ``locator``, based on a screenshot.

        ``scheme`` lists percentages of colours, e.g. ``> 60% #1f3a5f`` or
        ``40 to 60% white, < 10% black``. Colour names and ``#rrggbb`` both work.

        | Element Color Scheme Should Be    id:header    > 80% #1f3a5f
        """
        spec = SpecBuilder()
        element = spec.element(locator)
        spec.check(element, f"color-scheme {scheme}")
        self._run_builder(spec, f"{element} color scheme")

    # --- escape hatch ------------------------------------------------------------

    @keyword
    def element_should_satisfy_spec(self, locator: str, *specs: str, **references: str):
        """Checks ``locator`` against one or more raw Galen spec lines.

        For everything the other keywords do not cover. Other elements that the spec
        refers to are given as ``name=locator`` and can be used by that name in the spec.

        | Element Should Satisfy Spec    id:logo    inside header 16px left    width 120px    header=id:header
        | Element Should Satisfy Spec    css:.price    text matches "€ \\\\d+,\\\\d{2}"
        """
        if not specs:
            raise ValueError("At least one spec line is required.")
        spec = SpecBuilder()
        for name, ref_locator in references.items():
            spec.named(name, ref_locator)
        element = spec.element(locator)
        spec.check(element, *specs)
        self._run_builder(spec, f"{element} spec")
