"""Builds small Galen spec documents for the layout keywords."""

from GalenLibrary.locators import SPECIAL_OBJECTS, object_name, to_galen


class SpecBuilder:
    def __init__(self):
        self._objects: list = []  # (name, galen type, value)
        self._names: dict = {}
        self._taken: set = set()
        self._blocks: list = []

    def element(self, locator: str) -> str:
        """Registers a single element and returns its Galen object name."""
        key = str(locator).strip()
        if key in self._names:
            return self._names[key]
        galen_type, value = to_galen(key)
        if galen_type in SPECIAL_OBJECTS:
            self._names[key] = galen_type
            return galen_type
        name = object_name(key, self._taken)
        self._objects.append((name, galen_type, value))
        self._names[key] = name
        return name

    def named(self, name: str, locator: str) -> str:
        """Registers an element under an explicit name (for raw spec lines)."""
        galen_type, value = to_galen(locator)
        if galen_type in SPECIAL_OBJECTS:
            raise ValueError(
                f"'{name}': screen and viewport are always available, no need to pass them."
            )
        self._taken.add(name)
        self._objects.append((name, galen_type, value))
        self._names[str(locator).strip()] = name
        return name

    def elements(self, locator: str) -> str:
        """Registers a locator matching several elements; returns the ``name-*`` pattern."""
        galen_type, value = to_galen(locator)
        if galen_type in SPECIAL_OBJECTS:
            raise ValueError(f"'{locator}' cannot be used as a list of elements.")
        name = object_name(locator, self._taken)
        self._objects.append((f"{name}-*", galen_type, value))
        return f"{name}-*"

    def check(self, name: str, *specs: str) -> "SpecBuilder":
        lines = [f"    {name}:"] + [f"        {spec}" for spec in specs]
        self._blocks.append("\n".join(lines))
        return self

    def for_each_pair(self, pattern: str, spec_template: str) -> "SpecBuilder":
        """Applies ``spec_template`` (with ``{next}``) to every element and its next sibling."""
        spec = spec_template.format(next="${nextItem}")
        self._blocks.append(
            f"    @forEach [{pattern}] as item, next as nextItem\n"
            f"        ${{item}}:\n"
            f"            {spec}"
        )
        return self

    def render(self) -> str:
        lines = []
        if self._objects:
            lines.append("@objects")
            lines += [f"    {n}    {t}    {v}" for n, t, v in self._objects]
            lines.append("")
        lines += ["= Check =", *self._blocks, ""]
        return "\n".join(lines)
