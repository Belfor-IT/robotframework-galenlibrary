"""Visual regression keywords: compare (parts of) the page with baseline screenshots."""

import os
import re
from typing import Optional, Union

from robot.api import logger
from robot.api.deco import keyword
from robot.utils import is_truthy

from GalenLibrary.base import GalenContext, LayoutValidationError, robot_variable, slug
from GalenLibrary.locators import as_dto
from GalenLibrary.pending import PendingBaselines

LocatorList = Union[list, str, None]

DEFAULT_SUBFOLDER = "{browser}-{platform}-{width}x{height}"


class MissingBaselineError(LayoutValidationError):
    """The test goes on, so one run collects the screenshots of all missing baselines."""

    ROBOT_CONTINUE_ON_FAILURE = True


_SUBFOLDER_FIELDS = {"browser": "chrome", "platform": "linux", "width": 1, "height": 1}


def parse_max_difference(value) -> tuple:
    """``2%`` -> ``("percent", 2.0)``; ``50px`` or ``50`` -> ``("pixels", 50)``."""
    text = str(value).strip().lower().replace(" ", "")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(%|px)?", text)
    if not match:
        raise ValueError(f"max_difference must look like '1%' or '50px', got '{value}'.")
    number, unit = float(match.group(1)), match.group(2)
    if unit == "%":
        return ("percent", number)
    return ("pixels", int(number))


class VisualKeywords(GalenContext):
    def _init_visual(
        self, baseline_dir, baseline_subfolder, update_baselines, missing_baseline, tolerance
    ):
        self._baseline_dir = baseline_dir
        self._baseline_subfolder = self._check_subfolder(baseline_subfolder)
        self._update_baselines = is_truthy(update_baselines)
        self._missing_baseline = self._check_missing_mode(missing_baseline)
        self._default_tolerance = int(tolerance)
        self._test_pending: list = []

    @staticmethod
    def _check_subfolder(pattern) -> str:
        pattern = "" if pattern is None or str(pattern).upper() == "NONE" else str(pattern)
        try:
            pattern.format(**_SUBFOLDER_FIELDS)
        except (KeyError, IndexError, ValueError) as e:
            raise ValueError(
                f"baseline_subfolder '{pattern}' may only use "
                "{browser}, {platform}, {width} and {height}."
            ) from e
        return pattern

    @staticmethod
    def _check_missing_mode(mode) -> str:
        mode = str(mode).strip().lower()
        if mode not in ("create", "fail"):
            raise ValueError("missing_baseline must be 'create' or 'fail'.")
        return mode

    # --- configuration -----------------------------------------------------------

    def _get_baseline_root(self) -> str:
        if self._baseline_dir:
            return os.path.abspath(self._baseline_dir)
        return os.path.join(robot_variable("${EXECDIR}") or os.getcwd(), "baselines")

    def _missing_mode(self) -> str:
        override = robot_variable("${GALEN_MISSING_BASELINE}", None)
        return self._check_missing_mode(override) if override else self._missing_baseline

    def _environment(self) -> dict:
        driver = self._get_driver()
        capabilities = getattr(driver, "capabilities", None) or {}
        size = driver.get_window_size()
        return {
            "browser": slug(capabilities.get("browserName") or "browser"),
            "platform": slug(
                capabilities.get("platformName") or capabilities.get("platform") or "unknown"
            ),
            "width": size["width"],
            "height": size["height"],
        }

    def _baseline_folder(self) -> str:
        root = self._get_baseline_root()
        if not self._baseline_subfolder:
            return root
        subfolder = self._baseline_subfolder.format(**self._environment())
        return os.path.normpath(os.path.join(root, subfolder))

    def _pending(self) -> PendingBaselines:
        output_dir = robot_variable("${OUTPUT DIR}") or os.path.dirname(self._get_report_root())
        return PendingBaselines.for_root(os.path.join(output_dir, "galen-pending"))

    def _keep_for_approval(self, baseline: str, reason: str, source=None) -> None:
        pending = self._pending()
        root = self._get_baseline_root()
        target = pending.add(root, baseline, reason, robot_variable("${TEST NAME}"), source=source)
        if target:
            self._test_pending.append(target)
            logger.info(f"New screenshot kept for approval: {target}")
        else:
            owner = pending.owner(root, baseline)
            logger.info(
                f"Not kept for approval: the screenshot of earlier test '{owner}' is kept for "
                f"'{os.path.basename(baseline)}'."
            )

    def _start_test_pending(self) -> None:
        self._test_pending = []

    def _end_test_pending(self, passed: bool) -> None:
        if passed and self._test_pending:
            self._pending().discard(self._test_pending)
        self._test_pending = []

    def _updating(self) -> bool:
        return self._update_baselines or is_truthy(
            robot_variable("${GALEN_UPDATE_BASELINES}", False)
        )

    def _baseline_path(self, name: Optional[str], locator: str) -> str:
        if not name:
            context = (
                robot_variable("${TEST NAME}") or robot_variable("${SUITE NAME}") or "baseline"
            )
            target = "page" if locator in ("viewport", "screen") else slug(locator, 40)
            name = f"{slug(context)}-{target}"
        if not name.lower().endswith(".png"):
            name += ".png"
        return os.path.join(self._baseline_folder(), name)

    @keyword
    def set_baseline_directory(self, path: str) -> str:
        """Sets the folder with baseline images. Returns the previous value.

        Default is ``${EXECDIR}/baselines`` or the ``baseline_dir`` import argument. The
        images are stored in a subfolder per browser, platform and window size, see the
        ``baseline_subfolder`` import argument.
        """
        previous = self._get_baseline_root()
        self._baseline_dir = path
        return previous

    # --- keywords ----------------------------------------------------------------

    @keyword
    def capture_baseline(
        self, locator: str = "viewport", name: Optional[str] = None, full_page: bool = False
    ) -> str:
        """Takes a screenshot of ``locator`` and stores it as baseline ``name``.

        Overwrites an existing baseline. Normally not needed: `Element Should Match Baseline`
        creates a missing baseline automatically. Returns the path of the image.

        | Capture Baseline    id:header    name=header-desktop
        | Capture Baseline    name=homepage-desktop
        """
        path = self._baseline_path(name, locator)
        result = self._bridge.capture(
            locator=as_dto(locator), image_path=path, full_page=full_page, **self._session()
        )
        logger.info(f"Baseline saved: {path} ({result['width']}x{result['height']})")
        self._log_images([("Baseline", path)])
        return path

    @keyword
    def element_should_match_baseline(
        self,
        locator: str,
        name: Optional[str] = None,
        max_difference: str = "0%",
        tolerance: Optional[int] = None,
        ignore: LocatorList = None,
        analyze_offset: int = 0,
        full_page: bool = False,
    ) -> dict:
        """Compares ``locator`` with its baseline screenshot.

        - ``name``: baseline file name in the baseline folder (``.png`` is added).
          Default is the test name plus the locator, e.g. ``header-layout-id-header.png``.
        - ``max_difference``: how much may differ before the keyword fails: a percentage
          of the pixels (``1%``, ``0.5%``) or a number of pixels (``50px``). Default ``0%``.
        - ``tolerance``: how different a single pixel may be before it counts as
          different: the sum of the red, green and blue differences, 0-765. Default
          ``25`` (or the ``tolerance`` import argument). Use a higher value for
          anti-aliased text that differs slightly between machines.
        - ``ignore``: locator(s) of parts that should not be compared, such as a clock or
          a rotating banner. A list or a comma separated string.
        - ``analyze_offset``: also accept the image when it is shifted by up to this many
          pixels.
        - ``full_page``: only needed for elements that are higher or wider than the window.
          The screenshot is then made by scrolling and stitching, which repeats sticky and
          fixed elements (such as a sticky header) in the image. Only the window is scrolled,
          so it does not work on pages where a container (e.g. ``div.content-body`` with
          ``overflow: auto``) scrolls instead of the window; compare smaller parts there.

        An element that is out of view, far down a long page or in a scrolling container, is
        scrolled into view automatically (centred) and the scroll positions of the window and
        the containers are restored afterwards. With ``full_page=True`` an element that fits in
        the window is handled the same way.

        When the baseline does not exist yet it is created and the keyword passes with a
        warning. With ``missing_baseline=fail`` (import argument, or
        ``--variable GALEN_MISSING_BASELINE:fail``) it fails instead, but the test goes on, so
        the screenshots of all missing baselines are collected in one run. Run with
        ``--variable GALEN_UPDATE_BASELINES:True`` to replace all baselines.

        When the test fails, the new screenshot is kept in ``${OUTPUT DIR}/galen-pending``.
        After checking the heatmap, ``python -m GalenLibrary.approve results`` makes those
        screenshots the new baselines. See `Baselines in CI`.

        On every comparison the baseline, the actual image and a heatmap are written to the
        Galen report folder and shown in the log. In the heatmap the actual image is grey,
        differences are green (small), yellow (medium) or red (large), ignored parts are
        blue and a red frame shows where the differences are.

        Returns a dictionary with ``percentage``, ``pixels``, ``baseline``, ``actual``,
        ``heatmap`` and ``created`` (``True`` when the baseline was just created).

        | Element Should Match Baseline    id:header
        | Element Should Match Baseline    id:products    name=products-desktop    max_difference=1%
        | Element Should Match Baseline    id:hero    ignore=id:clock    tolerance=60
        """
        return self._match_baseline(
            locator, name, max_difference, tolerance, ignore, analyze_offset, full_page
        )

    @keyword
    def page_should_match_baseline(
        self,
        name: Optional[str] = None,
        max_difference: str = "0%",
        tolerance: Optional[int] = None,
        ignore: LocatorList = None,
        analyze_offset: int = 0,
        full_page: bool = False,
    ) -> dict:
        """Compares the visible part of the page (or the whole page with ``full_page=True``)
        with its baseline. Arguments as in `Element Should Match Baseline`.

        A whole page screenshot is made by scrolling and stitching: sticky and fixed elements
        appear several times, and a page that gets longer no longer matches the baseline size.
        For long pages, comparing the parts with `Element Should Match Baseline` is usually
        more reliable.

        | Page Should Match Baseline    homepage-desktop    max_difference=0.5%
        | Page Should Match Baseline    homepage-full    full_page=True    ignore=css:.ad
        """
        locator = "screen" if full_page else "viewport"
        return self._match_baseline(
            locator, name, max_difference, tolerance, ignore, analyze_offset, full_page
        )

    # --- implementation ----------------------------------------------------------

    def _match_baseline(
        self, locator, name, max_difference, tolerance, ignore, analyze_offset, full_page
    ) -> dict:
        kind, limit = parse_max_difference(max_difference)
        tolerance = self._default_tolerance if tolerance in (None, "") else int(tolerance)
        baseline = self._baseline_path(name, locator)
        session = self._session()
        label = os.path.basename(baseline)

        if self._updating() or not os.path.isfile(baseline):
            if (
                not os.path.isfile(baseline)
                and self._missing_mode() == "fail"
                and not self._updating()
            ):
                pending = self._pending().path_for(self._get_baseline_root(), baseline)
                if self._pending().owner(self._get_baseline_root(), baseline) is None:
                    self._bridge.capture(
                        locator=as_dto(locator), image_path=pending, full_page=full_page, **session
                    )
                    self._keep_for_approval(baseline, "missing")
                    self._log_images([("New screenshot (for approval)", pending)])
                raise MissingBaselineError(
                    f"Baseline '{baseline}' does not exist. The screenshot is kept for approval: "
                    f"{pending}"
                )
            action = "updated" if os.path.isfile(baseline) else "created"
            self._bridge.capture(
                locator=as_dto(locator), image_path=baseline, full_page=full_page, **session
            )
            logger.warn(f"Baseline {action}: {baseline}")
            self._log_images([("New baseline", baseline)])
            return {
                "percentage": 0.0,
                "pixels": 0,
                "baseline": baseline,
                "actual": baseline,
                "heatmap": None,
                "created": True,
            }

        output_dir = self._next_report_dir(f"baseline {os.path.splitext(label)[0]}")
        result = self._bridge.compare(
            locator=as_dto(locator),
            image_path=baseline,
            output_dir=output_dir,
            tolerance=tolerance,
            analyze_offset=int(analyze_offset),
            ignore=[as_dto(loc) for loc in self._split_tags(ignore)],
            full_page=full_page,
            **session,
        )
        images = [
            ("Baseline", result.get("baselineCopyPath")),
            ("Actual", result.get("actualPath")),
            ("Heatmap", result.get("heatmapPath")),
        ]
        summary = {
            "percentage": round(result.get("percentage", 0.0), 3),
            "pixels": result.get("pixels", 0),
            "baseline": baseline,
            "actual": result.get("actualPath"),
            "heatmap": result.get("heatmapPath"),
            "created": False,
        }

        if result.get("sizeMismatch"):
            self._log_images(images, level="INFO")
            self._keep_for_approval(baseline, "size", source=result.get("actualPath"))
            raise LayoutValidationError(
                f"'{locator}' has size {result['width']}x{result['height']} but baseline "
                f"'{label}' is {result['baselineWidth']}x{result['baselineHeight']}. "
                "Update the baseline if this change is intended."
            )

        allowed = f"{limit:g}%" if kind == "percent" else f"{limit}px"
        found = f"{summary['percentage']:g}% ({summary['pixels']} px)"
        exceeded = summary["percentage"] > limit if kind == "percent" else summary["pixels"] > limit
        self._log_images(images)
        if exceeded:
            self._keep_for_approval(baseline, "changed", source=result.get("actualPath"))
            raise LayoutValidationError(
                f"'{locator}' differs from baseline '{label}': {found} mismatching, "
                f"max allowed {allowed}. See the heatmap in the log."
            )
        logger.info(
            f"'{locator}' matches baseline '{label}': {found} mismatching, max allowed {allowed}."
        )
        return summary
