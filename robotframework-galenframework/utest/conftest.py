from pathlib import Path
from types import SimpleNamespace

import pytest

from GalenLibrary import GalenLibrary
from GalenLibrary.bridge import LayoutResult


class FakeBridge:
    """Records calls instead of talking to Java. Keeps the generated spec text."""

    def __init__(self):
        self.layout_result = LayoutResult(0, 0)
        self.compare_result = {"percentage": 0.0, "pixels": 0}
        self.calls = []
        self.specs = []

    def check_layout(self, **kwargs):
        self.calls.append(("check_layout", kwargs))
        self.specs.append(Path(kwargs["spec_path"]).read_text(encoding="utf-8"))
        return self.layout_result

    def capture(self, **kwargs):
        self.calls.append(("capture", kwargs))
        Path(kwargs["image_path"]).parent.mkdir(parents=True, exist_ok=True)
        Path(kwargs["image_path"]).write_bytes(b"png")
        return {"path": kwargs["image_path"], "width": 10, "height": 10}

    def compare(self, **kwargs):
        self.calls.append(("compare", kwargs))
        actual = Path(kwargs["output_dir"]) / "actual.png"
        actual.parent.mkdir(parents=True, exist_ok=True)
        actual.write_bytes(b"new png")
        return {"actualPath": str(actual), **self.compare_result}

    def close(self):
        pass


def selenium4_executor(url="http://localhost:9515"):
    return SimpleNamespace(_client_config=SimpleNamespace(remote_server_addr=url))


class FakeDriver:
    def __init__(self, executor=None):
        self.session_id = "sess-42"
        self.command_executor = executor or selenium4_executor()
        self.capabilities = {"browserName": "chrome", "platformName": "linux"}
        self.window_size = {"width": 1280, "height": 800}

    def get_window_size(self):
        return dict(self.window_size)


@pytest.fixture
def make_library(tmp_path):
    def factory(executor=None, **kwargs):
        # Most tests do not care about the subfolder per environment.
        kwargs.setdefault("baseline_subfolder", "NONE")
        lib = GalenLibrary(
            report_dir=str(tmp_path / "reports"), baseline_dir=str(tmp_path / "baselines"), **kwargs
        )
        lib._bridge = FakeBridge()
        lib.driver = FakeDriver(executor)
        lib._get_driver = lambda: lib.driver
        return lib

    return factory


@pytest.fixture
def spec(tmp_path):
    path = tmp_path / "home.gspec"
    path.write_text("@objects\n")
    return str(path)
