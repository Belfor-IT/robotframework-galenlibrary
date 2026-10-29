"""Approves the screenshots of failed baseline comparisons as new baselines.

    python -m GalenLibrary.approve [OUTPUT_DIR] [--baselines DIR] [--list] [PATTERN ...]

``OUTPUT_DIR`` is the Robot output folder (default ``results``) or its ``galen-pending``
folder. ``PATTERN`` limits approval to matching baselines, e.g. ``"*/header-*"``.
``--baselines`` overrides the baseline folder stored in the manifest, which is needed when
the results come from another machine (a CI artifact).
"""

import argparse
import fnmatch
import os
import shutil
import sys

from GalenLibrary.pending import read_manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m GalenLibrary.approve",
        description="Copy screenshots of failed baseline comparisons over the baselines.",
    )
    parser.add_argument("output", nargs="?", default="results", help="Robot output folder")
    parser.add_argument("patterns", nargs="*", help="only baselines matching these patterns")
    parser.add_argument("--baselines", help="baseline folder (default: as stored in the run)")
    parser.add_argument("--list", action="store_true", help="only show what would be approved")
    args = parser.parse_args(argv)

    root, entries = read_manifest(args.output)
    if root is None:
        print(f"Nothing to approve: no galen-pending/pending.json in '{args.output}'.")
        return 0
    if args.patterns:
        entries = [
            e for e in entries if any(fnmatch.fnmatch(e["baseline"], p) for p in args.patterns)
        ]
    if not entries:
        print("Nothing to approve.")
        return 0

    for entry in entries:
        baseline_root = args.baselines or entry["baseline_root"]
        if not args.baselines and not os.path.isdir(baseline_root):
            print(
                f"Baseline folder '{baseline_root}' does not exist here; "
                "use --baselines to point to it.",
                file=sys.stderr,
            )
            return 2
        source = os.path.join(root, entry["pending"])
        target = os.path.join(baseline_root, entry["baseline"])
        print(f"{entry['reason']:>9}  {entry['baseline']}  ({entry['test'] or 'no test'})")
        if not args.list:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(source, target)

    verb = "Would approve" if args.list else "Approved"
    print(f"{verb} {len(entries)} baseline(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
