"""Talks to the Galen Java engine (``galen-robot-bridge.jar``).

The jar runs as one long-lived ``java -jar ... --server`` process: requests and responses are
exchanged as one JSON document per line over stdin/stdout. Starting Java only once keeps every
keyword fast, also when a test contains many layout checks.
"""

import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

BUNDLED_JAR = Path(__file__).parent / "java" / "galen-robot-bridge.jar"


class GalenBridgeError(RuntimeError):
    """Raised when Galen itself could not run a check (not for layout differences)."""


@dataclass
class LayoutMessage:
    message: str
    place: Optional[str] = None
    warning: bool = False

    def __str__(self) -> str:
        return f"{self.message} ({self.place})" if self.place else self.message


@dataclass
class LayoutResult:
    errors: int
    warnings: int
    messages: list = field(default_factory=list)
    report_path: Optional[str] = None

    @property
    def error_messages(self) -> list:
        return [m for m in self.messages if not m.warning]

    @property
    def warning_messages(self) -> list:
        return [m for m in self.messages if m.warning]

    def to_dict(self) -> dict:
        return {
            "errors": self.errors,
            "warnings": self.warnings,
            "error_messages": [str(m) for m in self.error_messages],
            "warning_messages": [str(m) for m in self.warning_messages],
            "report_path": self.report_path,
        }

    @classmethod
    def from_json(cls, data: dict) -> "LayoutResult":
        return cls(
            errors=data.get("errors", 0),
            warnings=data.get("warnings", 0),
            messages=[
                LayoutMessage(m.get("message", ""), m.get("place"), bool(m.get("warning")))
                for m in data.get("messages", [])
            ],
            report_path=data.get("reportPath"),
        )


def find_java(java_path: Optional[str] = None) -> str:
    if java_path:
        return java_path
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        executable = Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java")
        if executable.is_file():
            return str(executable)
    found = shutil.which("java")
    if not found:
        raise GalenBridgeError(
            "Java executable not found. Install Java 11 or newer, set JAVA_HOME "
            "or pass 'java_path' when importing GalenLibrary."
        )
    return found


def find_jar(jar_path: Optional[str] = None) -> str:
    candidate = jar_path or os.environ.get("GALEN_BRIDGE_JAR") or str(BUNDLED_JAR)
    if not Path(candidate).is_file():
        raise GalenBridgeError(
            f"Galen bridge jar not found: {candidate}. Reinstall robotframework-galenframework "
            "or set GALEN_BRIDGE_JAR."
        )
    return candidate


class GalenBridge:
    def __init__(
        self,
        java_path: Optional[str] = None,
        jar_path: Optional[str] = None,
        jvm_options: Optional[list] = None,
        timeout: float = 300,
    ):
        self.java_path = java_path
        self.jar_path = jar_path
        self.jvm_options = list(jvm_options or [])
        self.timeout = timeout
        self._process: Optional[subprocess.Popen] = None
        self._responses: queue.Queue = queue.Queue()
        self._stderr_file = None
        self._lock = threading.Lock()

    # --- process management ----------------------------------------------------

    def command(self) -> list:
        return [
            find_java(self.java_path),
            "-Djava.awt.headless=true",
            *self.jvm_options,
            "-jar",
            find_jar(self.jar_path),
            "--server",
        ]

    def _start(self) -> None:
        self._stderr_file = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")
        self._responses = queue.Queue()
        self._process = subprocess.Popen(
            self.command(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._stderr_file,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        threading.Thread(target=self._read_responses, args=(self._process,), daemon=True).start()

    def _read_responses(self, process: subprocess.Popen) -> None:
        for line in process.stdout:
            self._responses.put(line)
        self._responses.put(None)  # process ended

    def _stderr_tail(self, lines: int = 30) -> str:
        if not self._stderr_file:
            return ""
        try:
            self._stderr_file.seek(0)
            return "".join(self._stderr_file.readlines()[-lines:])
        except (OSError, ValueError):
            return ""

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def close(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        try:
            process.stdin.close()
            process.wait(timeout=5)
        except Exception:
            process.kill()
        if self._stderr_file:
            self._stderr_file.close()
            self._stderr_file = None

    # --- requests ----------------------------------------------------------------

    def request(self, payload: dict) -> Any:
        with self._lock:
            if not self.running:
                self._start()
            try:
                self._process.stdin.write(json.dumps(payload) + "\n")
                self._process.stdin.flush()
            except OSError as e:
                stderr = self._stderr_tail()
                self.close()
                raise GalenBridgeError(f"Galen engine stopped unexpectedly:\n{stderr}") from e
            try:
                line = self._responses.get(timeout=self.timeout)
            except queue.Empty:
                self.close()
                raise GalenBridgeError(
                    f"Galen check timed out after {self.timeout} seconds"
                ) from None
            if line is None:
                stderr = self._stderr_tail()
                self.close()
                raise GalenBridgeError(f"Galen engine stopped unexpectedly:\n{stderr}")
        response = json.loads(line)
        if not response.get("ok"):
            raise GalenBridgeError(f"Galen check failed:\n{response.get('exception')}")
        return response.get("result")

    def check_layout(
        self,
        executor_url: str,
        session_id: str,
        spec_path: str,
        included_tags: Optional[list] = None,
        excluded_tags: Optional[list] = None,
        properties: Optional[dict] = None,
        js_variables: Optional[dict] = None,
        report_dir: Optional[str] = None,
        title: Optional[str] = None,
        report_only_on_failure: bool = False,
        full_page: bool = False,
    ) -> LayoutResult:
        data = self.request(
            {
                "command": "checkLayout",
                "executorUrl": executor_url,
                "sessionId": session_id,
                "specPath": spec_path,
                "includedTags": list(included_tags or []),
                "excludedTags": list(excluded_tags or []),
                "properties": {str(k): str(v) for k, v in (properties or {}).items()},
                "jsVariables": dict(js_variables or {}),
                "reportDir": report_dir,
                "reportOnlyOnFailure": report_only_on_failure,
                "title": title,
                "fullPage": full_page,
            }
        )
        return LayoutResult.from_json(data)

    def capture(
        self,
        executor_url: str,
        session_id: str,
        locator: dict,
        image_path: str,
        full_page: bool = False,
    ) -> dict:
        return self.request(
            {
                "command": "capture",
                "executorUrl": executor_url,
                "sessionId": session_id,
                "locator": locator,
                "imagePath": image_path,
                "fullPage": full_page,
            }
        )

    def compare(
        self,
        executor_url: str,
        session_id: str,
        locator: dict,
        image_path: str,
        output_dir: str,
        tolerance: int = 25,
        analyze_offset: int = 0,
        ignore: Optional[list] = None,
        full_page: bool = False,
    ) -> dict:
        return self.request(
            {
                "command": "compare",
                "executorUrl": executor_url,
                "sessionId": session_id,
                "locator": locator,
                "imagePath": image_path,
                "outputDir": output_dir,
                "tolerance": tolerance,
                "analyzeOffset": analyze_offset,
                "ignore": list(ignore or []),
                "fullPage": full_page,
            }
        )
