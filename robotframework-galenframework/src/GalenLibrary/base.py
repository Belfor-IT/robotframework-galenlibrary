"""Shared state and helpers for the GalenLibrary keyword classes."""

import html
import itertools
import os
import re
import shutil
import tempfile
from typing import Optional, Union

from robot.api import logger
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError

from GalenLibrary.bridge import GalenBridge, LayoutResult
from GalenLibrary.specs import SpecBuilder

TagList = Union[list, str, None]

# Shared by all library instances, so report folders of different suites never collide.
_REPORT_COUNTER = itertools.count(1)
# Default report folders already emptied in this run (stale reports of earlier runs are removed).
_CLEANED_REPORT_ROOTS: set = set()


class LayoutValidationError(AssertionError):
    ROBOT_SUPPRESS_NAME = True


def slug(text: str, limit: int = 60) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", str(text)).strip("-").lower()[:limit] or "check"


def px(value) -> str:
    """``10`` -> ``10px``; anything else (``10 to 20px``, ``~ 5px``, ``50% of screen/width``) as is."""
    text = str(value).strip()
    return f"{text}px" if re.fullmatch(r"-?\d+(\.\d+)?", text) else text


def robot_variable(name: str, default=None):
    try:
        return BuiltIn().get_variable_value(name, default)
    except RobotNotRunningError:
        return default


class GalenContext:
    """Base class: owns the Java bridge, the report folders and the link to SeleniumLibrary."""

    def __init__(
        self,
        report_dir: Optional[str],
        java_path: Optional[str],
        jar_path: Optional[str],
        timeout: float,
        selenium_library: str,
    ):
        self._report_dir = report_dir
        self._selenium_library = selenium_library
        self._bridge = GalenBridge(java_path=java_path, jar_path=jar_path, timeout=float(timeout))
        self._spec_dir: Optional[str] = None

    # --- lifecycle ---------------------------------------------------------------

    def _close_galen(self) -> None:
        self._bridge.close()
        if self._spec_dir:
            shutil.rmtree(self._spec_dir, ignore_errors=True)
            self._spec_dir = None

    # --- browser -----------------------------------------------------------------

    def _get_driver(self):
        try:
            selenium = BuiltIn().get_library_instance(self._selenium_library)
        except RuntimeError as e:
            raise RuntimeError(
                f"GalenLibrary needs '{self._selenium_library}' to be imported "
                "and a browser to be open."
            ) from e
        return selenium.driver

    @staticmethod
    def _executor_url(driver) -> str:
        executor = driver.command_executor
        client_config = getattr(executor, "_client_config", None)
        url = getattr(client_config, "remote_server_addr", None) or getattr(executor, "_url", None)
        if not url:
            raise RuntimeError("Cannot determine the WebDriver URL of the current browser.")
        return url

    def _session(self) -> dict:
        driver = self._get_driver()
        return {"executor_url": self._executor_url(driver), "session_id": driver.session_id}

    # --- folders -----------------------------------------------------------------

    def _get_report_root(self) -> str:
        if self._report_dir:
            return os.path.abspath(self._report_dir)
        output_dir = robot_variable("${OUTPUT DIR}")
        root = os.path.join(output_dir or os.getcwd(), "galen-reports")
        if output_dir and root not in _CLEANED_REPORT_ROOTS:
            _CLEANED_REPORT_ROOTS.add(root)
            shutil.rmtree(root, ignore_errors=True)
        return root

    def _next_report_dir(self, title: str) -> str:
        return os.path.join(self._get_report_root(), f"{next(_REPORT_COUNTER):03d}-{slug(title)}")

    def _write_spec(self, builder: SpecBuilder) -> str:
        if not self._spec_dir:
            self._spec_dir = tempfile.mkdtemp(prefix="galen-specs-")
        path = os.path.join(self._spec_dir, f"check-{len(os.listdir(self._spec_dir)) + 1}.gspec")
        text = builder.render()
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        logger.debug(f"Generated Galen spec:\n{text}")
        return path

    # --- running checks ----------------------------------------------------------

    def _run_builder(self, builder: SpecBuilder, title: str) -> LayoutResult:
        """Runs a generated spec. Fails with Galen's messages when the layout is wrong."""
        spec_path = self._write_spec(builder)
        result = self._bridge.check_layout(
            spec_path=spec_path,
            report_dir=self._next_report_dir(title),
            title=title,
            report_only_on_failure=True,
            **self._session(),
        )
        self._log_layout_result(result, quiet=True)
        if result.errors > 0:
            raise LayoutValidationError("\n".join(str(m.message) for m in result.error_messages))
        return result

    # --- logging -----------------------------------------------------------------

    def _log_layout_result(self, result: LayoutResult, quiet: bool = False) -> None:
        if result.report_path:
            self._log_link("Galen report", result.report_path)
        for message in result.warning_messages:
            logger.warn(f"Galen: {message}")
        if result.errors or result.warnings:
            logger.info(f"Layout check: {result.errors} error(s), {result.warnings} warning(s)")
        elif not quiet:
            logger.info("Layout check passed")

    def _relative_to_log(self, path: str) -> str:
        log_file = robot_variable("${LOG FILE}")
        if not log_file or str(log_file).upper() == "NONE":
            return path
        try:
            return os.path.relpath(path, os.path.dirname(log_file)).replace(os.sep, "/")
        except ValueError:  # different drive on Windows
            return path

    def _log_link(self, label: str, path: str) -> None:
        href = self._relative_to_log(path)
        logger.info(
            f'{html.escape(label)}: <a href="{html.escape(href)}">{html.escape(path)}</a>',
            html=True,
        )

    def _log_images(self, images: list, level: str = "INFO") -> None:
        """Logs ``[(caption, path), ...]`` side by side in the Robot log."""
        cells = []
        for caption, path in images:
            if not path:
                continue
            href = html.escape(self._relative_to_log(path))
            cells.append(
                '<td style="vertical-align:top;padding:4px">'
                f"<b>{html.escape(caption)}</b><br>"
                f'<a href="{href}"><img src="{href}" style="max-width:360px;'
                'border:1px solid #ccc"></a></td>'
            )
        if cells:
            logger.write(f"<table><tr>{''.join(cells)}</tr></table>", level=level, html=True)

    @staticmethod
    def _split_tags(tags: TagList) -> list:
        if not tags:
            return []
        if isinstance(tags, str):
            tags = tags.split(",")
        return [str(t).strip() for t in tags if str(t).strip()]
