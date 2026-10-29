"""Translates SeleniumLibrary style locators into Galen locators (``id``, ``css`` or ``xpath``)."""

import re

SPECIAL_OBJECTS = ("screen", "viewport")
_RESERVED_NAMES = {"screen", "viewport", "global", "parent", "self"}
_STRATEGY = re.compile(r"^\s*([A-Za-z ]+?)\s*[:=]\s*(.+)$", re.DOTALL)


def xpath_literal(value: str) -> str:
    if '"' not in value:
        return f'"{value}"'
    if "'" not in value:
        return f"'{value}'"
    parts = value.split('"')
    return "concat(" + ", '\"', ".join(f'"{p}"' for p in parts) + ")"


def to_galen(locator: str) -> tuple:
    """Returns ``(type, value)`` where type is ``id``, ``css``, ``xpath`` or a special object.

    Supported: ``id:``, ``css:``, ``xpath:``, ``class:``, ``name:``, ``tag:``, ``link:``,
    ``partial link:``, xpath expressions starting with ``//`` or ``(//`` and the special
    objects ``screen`` and ``viewport``. Without a prefix, the element is matched by id
    or name, like SeleniumLibrary does.
    """
    text = str(locator).strip()
    if not text:
        raise ValueError("Locator cannot be empty.")
    if text in SPECIAL_OBJECTS:
        return (text, text)
    if text.startswith("//") or text.startswith("(//"):
        return ("xpath", text)

    match = _STRATEGY.match(text)
    if match:
        strategy = match.group(1).strip().lower()
        value = match.group(2).strip()
        if strategy == "id":
            return ("id", value)
        if strategy == "css":
            return ("css", value)
        if strategy == "xpath":
            return ("xpath", value)
        if strategy == "class":
            return ("css", "." + ".".join(value.split()))
        if strategy == "name":
            return ("xpath", f"//*[@name={xpath_literal(value)}]")
        if strategy == "tag":
            return ("css", value)
        if strategy == "link":
            return ("xpath", f"//a[normalize-space(.)={xpath_literal(value)}]")
        if strategy == "partial link":
            return ("xpath", f"//a[contains(normalize-space(.), {xpath_literal(value)})]")
        if strategy in ("dom", "jquery", "sizzle", "data", "default"):
            raise ValueError(
                f"Locator strategy '{strategy}' is not supported by GalenLibrary. "
                "Use id, css, xpath, class, name, tag, link or partial link."
            )
        # Unknown prefix: probably part of a css selector such as 'a:hover'. Fall through.

    literal = xpath_literal(text)
    return ("xpath", f"//*[@id={literal} or @name={literal}]")


def object_name(locator: str, taken: set) -> str:
    """A readable Galen object name for a locator, used in error messages."""
    galen_type, value = to_galen(locator)
    if galen_type in SPECIAL_OBJECTS:
        return galen_type
    base = value
    if galen_type == "xpath":
        ids = re.findall(r"@(?:id|name)\s*=\s*[\"']([^\"']+)", value)
        base = ids[0] if ids else "element"
    name = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower() or "element"
    if name[0].isdigit():
        name = "el-" + name
    if name in _RESERVED_NAMES:
        name += "-element"
    candidate, counter = name, 2
    while candidate in taken:
        candidate = f"{name}-{counter}"
        counter += 1
    taken.add(candidate)
    return candidate


def as_dto(locator: str) -> dict:
    galen_type, value = to_galen(locator)
    return {"type": galen_type, "value": value}
