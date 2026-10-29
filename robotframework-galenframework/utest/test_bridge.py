import json
import sys

import pytest

from GalenLibrary.bridge import GalenBridge, GalenBridgeError

# A stand-in for 'java -jar galen-robot-bridge.jar --server': answers one JSON line per request.
FAKE_SERVER = """
import json, sys
log = open({log!r}, "a")
for line in sys.stdin:
    request = json.loads(line)
    log.write(line); log.flush()
    command = request["command"]
    if command == "crash":
        sys.exit(3)
    if command == "hang":
        import time; time.sleep(30)
    if command == "boom":
        print(json.dumps({{"ok": False, "exception": "java.io.FileNotFoundException: spec"}}), flush=True)
        continue
    print(json.dumps({{"ok": True, "result": {result}}}), flush=True)
"""

LAYOUT_RESULT = {
    "errors": 1,
    "warnings": 1,
    "messages": [
        {"message": '"menu" is 5px below header', "place": "spec.gspec:12", "warning": False},
        {"message": '"logo" width is 99px', "place": None, "warning": True},
    ],
    "reportPath": "/tmp/report.html",
}


def make_bridge(tmp_path, result=LAYOUT_RESULT, timeout=10) -> GalenBridge:
    script = tmp_path / "fake_server.py"
    script.write_text(FAKE_SERVER.format(log=str(tmp_path / "requests.log"), result=repr(result)))
    bridge = GalenBridge(timeout=timeout)
    bridge.command = lambda: [sys.executable, str(script)]
    return bridge


def sent_requests(tmp_path) -> list:
    return [json.loads(line) for line in (tmp_path / "requests.log").read_text().splitlines()]


def test_parses_errors_and_warnings(tmp_path):
    bridge = make_bridge(tmp_path)
    try:
        result = bridge.check_layout("http://localhost:1", "abc", "spec.gspec")
    finally:
        bridge.close()

    assert result.errors == 1
    assert result.warnings == 1
    assert [str(m) for m in result.error_messages] == ['"menu" is 5px below header (spec.gspec:12)']
    assert [str(m) for m in result.warning_messages] == ['"logo" width is 99px']
    assert result.to_dict()["report_path"] == "/tmp/report.html"


def test_one_process_serves_many_requests(tmp_path):
    bridge = make_bridge(tmp_path)
    try:
        bridge.check_layout("http://localhost:1", "abc", "a.gspec")
        pid = bridge._process.pid
        bridge.check_layout("http://localhost:1", "abc", "b.gspec")
        assert bridge._process.pid == pid
    finally:
        bridge.close()
    assert [r["specPath"] for r in sent_requests(tmp_path)] == ["a.gspec", "b.gspec"]


def test_check_layout_request(tmp_path):
    bridge = make_bridge(tmp_path)
    try:
        bridge.check_layout(
            "http://localhost:9515",
            "session-1",
            "home.gspec",
            included_tags=["desktop"],
            excluded_tags=["wip"],
            properties={"x": 1},
            js_variables={"user": "bob"},
            report_dir="out",
            title="Home",
            report_only_on_failure=True,
        )
    finally:
        bridge.close()

    assert sent_requests(tmp_path)[0] == {
        "command": "checkLayout",
        "executorUrl": "http://localhost:9515",
        "sessionId": "session-1",
        "specPath": "home.gspec",
        "includedTags": ["desktop"],
        "excludedTags": ["wip"],
        "properties": {"x": "1"},
        "jsVariables": {"user": "bob"},
        "reportDir": "out",
        "reportOnlyOnFailure": True,
        "title": "Home",
        "fullPage": False,
    }


def test_compare_request(tmp_path):
    bridge = make_bridge(tmp_path, result={"percentage": 1.5})
    try:
        result = bridge.compare(
            "http://x",
            "s",
            {"type": "id", "value": "logo"},
            "base.png",
            "out",
            tolerance=40,
            ignore=[{"type": "css", "value": ".clock"}],
        )
    finally:
        bridge.close()
    assert result == {"percentage": 1.5}
    request = sent_requests(tmp_path)[0]
    assert request["command"] == "compare"
    assert request["tolerance"] == 40
    assert request["ignore"] == [{"type": "css", "value": ".clock"}]


def test_exception_from_java_raises(tmp_path):
    bridge = make_bridge(tmp_path)
    try:
        with pytest.raises(GalenBridgeError, match="FileNotFoundException"):
            bridge.request({"command": "boom"})
        assert bridge.running  # an error in one check does not stop the engine
    finally:
        bridge.close()


def test_crashed_engine_is_restarted(tmp_path):
    bridge = make_bridge(tmp_path)
    try:
        with pytest.raises(GalenBridgeError, match="stopped unexpectedly"):
            bridge.request({"command": "crash"})
        assert bridge.request({"command": "ping"}) == LAYOUT_RESULT
    finally:
        bridge.close()


def test_timeout(tmp_path):
    bridge = make_bridge(tmp_path, timeout=1)
    try:
        with pytest.raises(GalenBridgeError, match="timed out"):
            bridge.request({"command": "hang"})
        assert not bridge.running
    finally:
        bridge.close()


def test_missing_jar_gives_clear_error(tmp_path):
    bridge = GalenBridge(java_path=sys.executable, jar_path=str(tmp_path / "nope.jar"))
    with pytest.raises(GalenBridgeError, match="jar not found"):
        bridge.request({"command": "ping"})
