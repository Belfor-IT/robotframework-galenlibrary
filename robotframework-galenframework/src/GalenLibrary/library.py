import atexit
import os
from typing import Optional

from robot.api.deco import keyword, library

from GalenLibrary.base import LayoutValidationError, TagList
from GalenLibrary.layout_keywords import LayoutKeywords
from GalenLibrary.version import VERSION
from GalenLibrary.visual_keywords import DEFAULT_SUBFOLDER, VisualKeywords

__all__ = ["GalenLibrary", "LayoutValidationError"]


@library(scope="GLOBAL", version=VERSION, doc_format="ROBOT")
class GalenLibrary(LayoutKeywords, VisualKeywords):
    """Layout and visual testing for Robot Framework, powered by [http://galenframework.com|Galen Framework].

    GalenLibrary checks the page that is open in
    [https://robotframework.org/SeleniumLibrary/|SeleniumLibrary]. It does not open a
    browser of its own: the Galen engine (Java) attaches to the browser session that
    SeleniumLibrary started, so logged-in state, cookies, the window size and changes made
    earlier in the test are all preserved.

    There are three ways to test, which can be mixed freely:

    - *Layout keywords* such as `Element Should Be Below`, `Element Should Be Inside` and
      `Element Width Should Be`: no Galen knowledge needed.
    - *Baseline keywords* `Element Should Match Baseline` and `Page Should Match Baseline`:
      compare with a stored screenshot, with an allowed difference and a heatmap.
    - `Check Layout`: run a complete Galen spec file (``.gspec``), handy for full pages on
      several screen sizes.

    = Requirements =

    - Java 11 or newer, on the ``PATH`` or via ``JAVA_HOME`` (or the ``java_path`` import argument).
    - SeleniumLibrary with an open browser.

    = Locators =

    Locators are written like in SeleniumLibrary: ``id:header``, ``css:#menu a``,
    ``xpath://div[@class='card']``, ``class:card``, ``name:q``, ``tag:h1``,
    ``link:Contact`` and ``partial link:Cont``. A locator without prefix matches on id or
    name, and one starting with ``//`` is xpath. Two special values exist:
    ``screen`` (the whole page) and ``viewport`` (the visible part of the window).

    When a locator matches several elements, the first one is used, except in
    `Elements Should Be Aligned` where all matches are checked.

    = Distances and sizes =

    Distances and sizes use Galen's notation: ``16px`` (or just ``16``), ``10 to 20px``,
    ``~ 16px`` (about), ``> 10px``, ``< 30px``, and for sizes also
    ``50% of viewport/width``.

    = Example =

    | *** Settings ***
    | Library    SeleniumLibrary
    | Library    GalenLibrary
    |
    | *** Test Cases ***
    | Header On Desktop
    |     Open Browser                    https://example.com    chrome
    |     Set Window Size                 1280    800
    |     Element Height Should Be        id:header    70px
    |     Element Should Be Inside        id:logo      id:header    16px left
    |     Element Should Be Centered      id:logo      id:header    vertically
    |     Element Should Be Below         id:hero      id:header    0px
    |     Elements Should Be Aligned      css:.card
    |     Element Should Match Baseline   id:header    max_difference=1%
    |     [Teardown]                      Close Browser

    = Reports =

    Failing layout checks and every `Check Layout` write a Galen HTML report with a
    screenshot and the elements highlighted; baseline comparisons write the baseline,
    actual image and heatmap. Everything goes to ``${OUTPUT DIR}/galen-reports`` and is
    linked or shown in the Robot Framework log.

    = Baselines in CI =

    Baselines only match when they are made under the same conditions as the comparison:
    same browser version, operating system (font rendering) and window size. Therefore:

    - Create and compare baselines in one fixed environment, e.g. a Docker image that is
      used both locally and in the CI pipeline, and keep the baselines in version control.
    - Baselines are stored per environment, in a subfolder such as
      ``baselines/chrome-linux-1280x800/header.png`` (import argument
      ``baseline_subfolder``). Desktop and mobile sizes, or Chrome and Firefox, never mix.
    - In CI, run with ``--variable GALEN_MISSING_BASELINE:fail`` so a missing baseline fails
      instead of silently being created.

    When a comparison fails (difference too large, other size or missing baseline), the new
    screenshot is kept in ``${OUTPUT DIR}/galen-pending``, with the same folder layout as the
    baselines and a ``pending.json`` manifest. Screenshots of tests that pass after all,
    for example with `Run Keyword And Expect Error`, are removed again. After checking the
    heatmaps, approve them as new baselines:

    | python -m GalenLibrary.approve results                        # all
    | python -m GalenLibrary.approve results "*/header-*"           # only matching baselines
    | python -m GalenLibrary.approve results --list                 # only show
    | python -m GalenLibrary.approve ci-results --baselines baselines   # results of another machine

    The same command is available as ``galen-approve``.
    """

    ROBOT_LISTENER_API_VERSION = 3

    def __init__(
        self,
        report_dir: Optional[str] = None,
        baseline_dir: Optional[str] = None,
        baseline_subfolder: Optional[str] = DEFAULT_SUBFOLDER,
        update_baselines: bool = False,
        missing_baseline: str = "create",
        tolerance: int = 25,
        java_path: Optional[str] = None,
        jar_path: Optional[str] = None,
        timeout: float = 300,
        selenium_library: str = "SeleniumLibrary",
    ):
        """Library import arguments:

        - ``report_dir``: folder for Galen reports and comparison images. Default ``${OUTPUT DIR}/galen-reports``,
          which is emptied at the start of every run.
        - ``baseline_dir``: folder with baseline images. Default ``${EXECDIR}/baselines``.
        - ``baseline_subfolder``: subfolder per environment, default ``{browser}-{platform}-{width}x{height}``,
          e.g. ``chrome-linux-1280x800``. The width and height are the window size at the moment of
          the comparison. Use ``NONE`` to store all baselines directly in ``baseline_dir``.
        - ``update_baselines``: replace baselines instead of comparing. Also possible per run with
          ``--variable GALEN_UPDATE_BASELINES:True``.
        - ``missing_baseline``: ``create`` (default) stores a missing baseline and passes with a warning,
          ``fail`` fails the keyword. Also possible per run with ``--variable GALEN_MISSING_BASELINE:fail``.
        - ``tolerance``: default per-pixel colour tolerance for baseline comparisons (0-765, default 25).
        - ``java_path``: path to the ``java`` executable. Default ``JAVA_HOME`` or ``PATH``.
        - ``jar_path``: alternative Galen bridge jar, mainly for development.
        - ``timeout``: maximum time in seconds for a single check.
        - ``selenium_library``: name under which SeleniumLibrary was imported (when using ``AS``).

        | Library    GalenLibrary    baseline_dir=${CURDIR}/baselines    tolerance=40
        """
        super().__init__(report_dir, java_path, jar_path, timeout, selenium_library)
        self._init_visual(
            baseline_dir, baseline_subfolder, update_baselines, missing_baseline, tolerance
        )
        self.ROBOT_LIBRARY_LISTENER = self
        atexit.register(self._close_galen)

    # Listener methods, called by Robot Framework.
    def start_test(self, data, result):
        self._start_test_pending()

    def end_test(self, data, result):
        self._end_test_pending(passed=result.status != "FAIL")

    def close(self):
        """Called when the library goes out of scope."""
        self._close_galen()

    @keyword
    def set_galen_report_directory(self, path: str) -> str:
        """Sets the folder where Galen reports and comparison images are written. Returns the previous value."""
        previous = self._get_report_root()
        self._report_dir = path
        return previous

    @keyword
    def check_layout(
        self,
        spec: str,
        tags: TagList = None,
        exclude_tags: TagList = None,
        properties: Optional[dict] = None,
        variables: Optional[dict] = None,
        title: Optional[str] = None,
        fail_on_error: bool = True,
        full_page: bool = False,
    ) -> dict:
        """Checks the layout of the current page against a Galen ``spec`` file (``.gspec``).

        - ``tags``: tags to include (``@on`` sections), list or comma separated string.
        - ``exclude_tags``: tags to exclude.
        - ``properties``: dictionary of properties available in the spec.
        - ``variables``: dictionary of JavaScript variables available in the spec.
        - ``title``: title used in the Galen report. Default ``Check layout <spec>``.
        - ``fail_on_error``: when ``True`` (default) the keyword fails on layout errors.
          Warnings never fail the keyword.
        - ``full_page``: use a full page screenshot (needed for ``image`` specs below the fold).

        Returns a dictionary with ``errors``, ``warnings``, ``error_messages``,
        ``warning_messages`` and ``report_path``.

        | Check Layout    ${CURDIR}/specs/homepage.gspec    desktop
        | Check Layout    homepage.gspec    tags=mobile, logged-in    exclude_tags=wip
        | ${result} =     Check Layout    homepage.gspec    desktop    fail_on_error=False
        | Should Be Equal As Integers    ${result}[errors]    0
        """
        spec_path = self._resolve_spec(spec)
        included = self._split_tags(tags)
        excluded = self._split_tags(exclude_tags)
        title = title or f"Check layout {os.path.basename(spec_path)}"

        result = self._bridge.check_layout(
            spec_path=spec_path,
            included_tags=included,
            excluded_tags=excluded,
            properties=properties,
            js_variables=variables,
            report_dir=self._next_report_dir(title),
            title=title,
            full_page=full_page,
            **self._session(),
        )
        self._log_layout_result(result)
        if fail_on_error and result.errors > 0:
            raise LayoutValidationError(self._failure_message(spec_path, included, result))
        return result.to_dict()

    @staticmethod
    def _resolve_spec(spec: str) -> str:
        path = os.path.abspath(os.path.expanduser(spec))
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Galen spec file not found: {path}")
        return path

    @staticmethod
    def _failure_message(spec_path: str, tags: list, result) -> str:
        header = f"Layout check of '{os.path.basename(spec_path)}'"
        if tags:
            header += f" (tags: {', '.join(tags)})"
        lines = [f"{header} failed with {result.errors} error(s):"]
        lines += [f"- {m}" for m in result.error_messages]
        return "\n".join(lines)
