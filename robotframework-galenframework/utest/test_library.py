import re
from types import SimpleNamespace

import pytest

from GalenLibrary.bridge import LayoutMessage, LayoutResult
from GalenLibrary.library import LayoutValidationError


def test_passes_session_and_tags_to_bridge(make_library, spec):
    lib = make_library()

    result = lib.check_layout(spec, tags="desktop, logged-in", exclude_tags=["wip"])

    _, call = lib._bridge.calls[0]
    assert call["executor_url"] == "http://localhost:9515"
    assert call["session_id"] == "sess-42"
    assert call["included_tags"] == ["desktop", "logged-in"]
    assert call["excluded_tags"] == ["wip"]
    assert re.search(r"\d{3}-check-layout-home-gspec$", call["report_dir"])
    assert result["errors"] == 0


def test_supports_older_selenium_executor_url(make_library, spec):
    lib = make_library(executor=SimpleNamespace(_url="http://grid:4444/wd/hub"))
    lib.check_layout(spec)
    assert lib._bridge.calls[0][1]["executor_url"] == "http://grid:4444/wd/hub"


def test_fails_on_layout_errors(make_library, spec):
    lib = make_library()
    lib._bridge.layout_result = LayoutResult(
        1, 0, [LayoutMessage('"menu" is not below header', "home.gspec:7")]
    )

    with pytest.raises(LayoutValidationError) as error:
        lib.check_layout(spec, tags="desktop")

    assert "home.gspec' (tags: desktop) failed with 1 error(s)" in str(error.value)
    assert '- "menu" is not below header (home.gspec:7)' in str(error.value)


def test_fail_on_error_false_returns_result(make_library, spec):
    lib = make_library()
    lib._bridge.layout_result = LayoutResult(
        2, 1, [LayoutMessage("a"), LayoutMessage("b"), LayoutMessage("c", warning=True)]
    )

    returned = lib.check_layout(spec, fail_on_error=False)

    assert returned["errors"] == 2
    assert returned["error_messages"] == ["a", "b"]
    assert returned["warning_messages"] == ["c"]


def test_missing_spec_fails(make_library, tmp_path):
    with pytest.raises(FileNotFoundError):
        make_library().check_layout(str(tmp_path / "missing.gspec"))


def test_report_folders_are_unique_across_library_instances(make_library, spec):
    first, second = make_library(), make_library()
    first.check_layout(spec)
    second.check_layout(spec)
    dirs = [lib._bridge.calls[0][1]["report_dir"] for lib in (first, second)]
    assert dirs[0] != dirs[1]
