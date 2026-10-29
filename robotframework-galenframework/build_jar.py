"""Builds galen-robot-bridge.jar from the Galen sources in this repository and copies it into the
Python package, so that ``python -m build`` produces a wheel that contains the Galen engine.

Usage (from this folder):  python build_jar.py [--mvn path/to/mvn]
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
BUILT_JAR = REPO_ROOT / "galen-robot-bridge" / "target" / "galen-robot-bridge.jar"
PACKAGE_JAR = HERE / "src" / "GalenLibrary" / "java" / "galen-robot-bridge.jar"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mvn", default=shutil.which("mvn") or shutil.which("mvn.cmd"))
    args = parser.parse_args()
    if not args.mvn:
        print("Maven (mvn) not found on PATH; pass --mvn.", file=sys.stderr)
        return 1

    command = [
        args.mvn,
        "-B",
        "-f",
        str(REPO_ROOT / "pom.xml"),
        "-pl",
        "galen-robot-bridge",
        "-am",
        "package",
        "-DskipTests",
        # The npm/grunt build in galen-core only runs JavaScript unit tests; the report
        # resources it would produce are already checked in.
        "-Dskip.installnodenpm",
        "-Dskip.npm",
        "-Dgpg.skip",
    ]
    print(" ".join(command))
    subprocess.run(command, check=True)

    PACKAGE_JAR.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BUILT_JAR, PACKAGE_JAR)
    print(f"Copied {BUILT_JAR} -> {PACKAGE_JAR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
