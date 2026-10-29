import json
import os
from types import SimpleNamespace

import pytest

from GalenLibrary.approve import main as approve
from GalenLibrary.library import LayoutValidationError
from GalenLibrary.visual_keywords import parse_max_difference


@pytest.mark.parametrize(
    "value, expected",
    [
        ("0%", ("percent", 0.0)),
        ("1.5%", ("percent", 1.5)),
        ("50px", ("pixels", 50)),
        ("50", ("pixels", 50)),
        (" 2 % ", ("percent", 2.0)),
    ],
)
def test_parse_max_difference(value, expected):
    assert parse_max_difference(value) == expected


def test_parse_max_difference_rejects_garbage():
    with pytest.raises(ValueError):
        parse_max_difference("a lot")


def commands(lib):
    return [name for name, _ in lib._bridge.calls]


def test_missing_baseline_is_created(make_library, tmp_path):
    lib = make_library()
    result = lib.element_should_match_baseline("id:logo", name="logo")
    assert result["created"] is True
    assert commands(lib) == ["capture"]
    assert os.path.isfile(tmp_path / "baselines" / "logo.png")


def test_missing_baseline_can_fail(make_library):
    lib = make_library(missing_baseline="fail")
    with pytest.raises(AssertionError, match="does not exist"):
        lib.element_should_match_baseline("id:logo", name="logo")


def test_missing_baseline_mode_from_variable(make_library, monkeypatch):
    lib = make_library()
    monkeypatch.setattr(
        "GalenLibrary.visual_keywords.robot_variable",
        lambda name, default=None: "fail" if name == "${GALEN_MISSING_BASELINE}" else default,
    )
    with pytest.raises(AssertionError, match="does not exist"):
        lib.element_should_match_baseline("id:logo", name="logo")


def test_existing_baseline_is_compared(make_library):
    lib = make_library()
    lib.capture_baseline("id:logo", name="logo")
    lib._bridge.compare_result = {"percentage": 0.4, "pixels": 12}

    result = lib.element_should_match_baseline(
        "id:logo", name="logo", max_difference="1%", tolerance=40, ignore="id:clock, css:.ad"
    )

    assert result["percentage"] == 0.4
    _, call = lib._bridge.calls[-1]
    assert call["tolerance"] == 40
    assert call["locator"] == {"type": "id", "value": "logo"}
    assert call["ignore"] == [{"type": "id", "value": "clock"}, {"type": "css", "value": ".ad"}]


@pytest.mark.parametrize(
    "max_difference, percentage, pixels, fails",
    [
        ("0%", 0.0, 0, False),
        ("0%", 0.01, 1, True),
        ("1%", 1.0, 100, False),
        ("1%", 1.2, 120, True),
        ("100px", 5.0, 100, False),
        ("100px", 5.0, 101, True),
    ],
)
def test_max_difference(make_library, max_difference, percentage, pixels, fails):
    lib = make_library()
    lib.capture_baseline("id:logo", name="logo")
    lib._bridge.compare_result = {"percentage": percentage, "pixels": pixels}
    if fails:
        with pytest.raises(LayoutValidationError, match="differs from baseline 'logo.png'"):
            lib.element_should_match_baseline("id:logo", name="logo", max_difference=max_difference)
    else:
        lib.element_should_match_baseline("id:logo", name="logo", max_difference=max_difference)


def test_size_mismatch(make_library):
    lib = make_library()
    lib.capture_baseline("id:logo", name="logo")
    lib._bridge.compare_result = {
        "sizeMismatch": True,
        "width": 130,
        "height": 40,
        "baselineWidth": 120,
        "baselineHeight": 40,
    }
    with pytest.raises(
        LayoutValidationError, match="has size 130x40 but baseline 'logo.png' is 120x40"
    ):
        lib.element_should_match_baseline("id:logo", name="logo", max_difference="100%")


def test_update_baselines_recaptures(make_library):
    lib = make_library(update_baselines=True)
    lib.capture_baseline("id:logo", name="logo")
    result = lib.element_should_match_baseline("id:logo", name="logo")
    assert result["created"] is True
    assert commands(lib) == ["capture", "capture"]


def test_page_baseline_uses_viewport_or_screen(make_library):
    lib = make_library()
    lib.page_should_match_baseline("home")
    assert lib._bridge.calls[-1][1]["locator"] == {"type": "viewport", "value": "viewport"}
    lib.page_should_match_baseline("home-full", full_page=True)
    assert lib._bridge.calls[-1][1]["locator"] == {"type": "screen", "value": "screen"}
    assert lib._bridge.calls[-1][1]["full_page"] is True


def test_default_baseline_name(make_library, tmp_path):
    lib = make_library()
    path = lib.capture_baseline("css:#products .card")
    assert path == str(tmp_path / "baselines" / "baseline-css-products-card.png")


# --- subfolder per environment -----------------------------------------------------


def test_baselines_are_stored_per_environment(make_library, tmp_path):
    lib = make_library(baseline_subfolder="{browser}-{platform}-{width}x{height}")
    assert lib.capture_baseline("id:logo", name="logo") == str(
        tmp_path / "baselines" / "chrome-linux-1280x800" / "logo.png"
    )
    lib.driver.window_size = {"width": 375, "height": 812}
    lib.driver.capabilities = {"browserName": "MicrosoftEdge", "platformName": "Windows"}
    assert lib.capture_baseline("id:logo", name="logo") == str(
        tmp_path / "baselines" / "microsoftedge-windows-375x812" / "logo.png"
    )


def test_custom_subfolder(make_library, tmp_path):
    lib = make_library(baseline_subfolder="{browser}/{width}")
    path = lib.capture_baseline("id:logo", name="logo")
    assert path == str(tmp_path / "baselines" / "chrome" / "1280" / "logo.png")


def test_invalid_subfolder_is_rejected(make_library):
    with pytest.raises(ValueError, match="may only use"):
        make_library(baseline_subfolder="{browser}-{resolution}")


# --- screenshots kept for approval ---------------------------------------------------


def pending_manifest(tmp_path):
    path = tmp_path / "galen-pending" / "pending.json"
    return json.loads(path.read_text(encoding="utf-8"))["files"] if path.exists() else []


def failing_comparison(make_library, **kwargs):
    lib = make_library(baseline_subfolder="{browser}-{width}x{height}", **kwargs)
    lib.capture_baseline("id:logo", name="logo")
    lib._bridge.compare_result = {"percentage": 5.0, "pixels": 500}
    lib.start_test(None, None)
    with pytest.raises(LayoutValidationError):
        lib.element_should_match_baseline("id:logo", name="logo")
    return lib


def test_failed_comparison_keeps_new_screenshot(make_library, tmp_path):
    lib = failing_comparison(make_library)
    lib.end_test(None, SimpleNamespace(status="FAIL"))

    pending = tmp_path / "galen-pending" / "chrome-1280x800" / "logo.png"
    assert pending.read_bytes() == b"new png"
    [entry] = pending_manifest(tmp_path)
    assert entry["baseline"] == "chrome-1280x800/logo.png"
    assert entry["reason"] == "changed"
    assert entry["baseline_root"] == str(tmp_path / "baselines")


def test_screenshot_of_passing_test_is_discarded(make_library, tmp_path):
    lib = failing_comparison(make_library)
    lib.end_test(None, SimpleNamespace(status="PASS"))

    assert not (tmp_path / "galen-pending" / "chrome-1280x800").exists()
    assert pending_manifest(tmp_path) == []


def test_size_mismatch_is_kept_for_approval(make_library, tmp_path):
    lib = make_library()
    lib.capture_baseline("id:logo", name="logo")
    lib._bridge.compare_result = {
        "sizeMismatch": True,
        "width": 130,
        "height": 40,
        "baselineWidth": 120,
        "baselineHeight": 40,
    }
    with pytest.raises(LayoutValidationError):
        lib.element_should_match_baseline("id:logo", name="logo")
    assert [e["reason"] for e in pending_manifest(tmp_path)] == ["size"]


def test_missing_baseline_in_fail_mode_is_kept_for_approval(make_library, tmp_path):
    lib = make_library(missing_baseline="fail")
    with pytest.raises(AssertionError, match="kept for approval"):
        lib.element_should_match_baseline("id:logo", name="logo")
    assert (tmp_path / "galen-pending" / "logo.png").exists()
    assert not (tmp_path / "baselines" / "logo.png").exists()
    assert [e["reason"] for e in pending_manifest(tmp_path)] == ["missing"]


# --- approve command -----------------------------------------------------------------


def test_approve_copies_pending_over_baselines(make_library, tmp_path, capsys):
    failing_comparison(make_library)
    baseline = tmp_path / "baselines" / "chrome-1280x800" / "logo.png"
    assert baseline.read_bytes() == b"png"

    assert approve([str(tmp_path), "--list"]) == 0
    assert baseline.read_bytes() == b"png"
    assert "Would approve 1 baseline(s)." in capsys.readouterr().out

    assert approve([str(tmp_path)]) == 0
    assert baseline.read_bytes() == b"new png"


def test_approve_with_pattern_and_other_baseline_folder(make_library, tmp_path):
    failing_comparison(make_library)
    other = tmp_path / "checkout" / "baselines"

    assert approve([str(tmp_path / "galen-pending"), "*/nothing*", "--baselines", str(other)]) == 0
    assert not other.exists()
    assert approve([str(tmp_path), "*/logo*", "--baselines", str(other)]) == 0
    assert (other / "chrome-1280x800" / "logo.png").read_bytes() == b"new png"


def test_approve_without_pending_files(tmp_path, capsys):
    assert approve([str(tmp_path)]) == 0
    assert "Nothing to approve" in capsys.readouterr().out


def test_first_failing_test_keeps_its_screenshot(make_library, tmp_path):
    lib = failing_comparison(make_library)
    lib.end_test(None, SimpleNamespace(status="FAIL"))

    # A later test changes the page on purpose and fails on the same baseline.
    lib.start_test(None, None)
    lib._bridge.compare_result = {"percentage": 9.0, "pixels": 900, "actualPath": None}
    actual = tmp_path / "later.png"
    actual.write_bytes(b"changed page")
    lib._bridge.compare_result["actualPath"] = str(actual)
    with pytest.raises(LayoutValidationError):
        lib.element_should_match_baseline("id:logo", name="logo")
    lib.end_test(None, SimpleNamespace(status="PASS"))

    pending = tmp_path / "galen-pending" / "chrome-1280x800" / "logo.png"
    assert pending.read_bytes() == b"new png"
    assert len(pending_manifest(tmp_path)) == 1


def test_missing_baseline_is_captured_once(make_library):
    lib = make_library(missing_baseline="fail")
    for _ in range(2):
        with pytest.raises(AssertionError, match="does not exist"):
            lib.element_should_match_baseline("id:logo", name="logo")
    assert commands(lib) == ["capture"]


def test_missing_baseline_failure_lets_the_test_continue(make_library):
    lib = make_library(missing_baseline="fail")
    with pytest.raises(AssertionError) as error:
        lib.element_should_match_baseline("id:logo", name="logo")
    assert getattr(error.value, "ROBOT_CONTINUE_ON_FAILURE", False) is True
