"""Screenshots of failed baseline comparisons, kept so they can be approved as new baselines.

Failed comparisons write the new screenshot to ``${OUTPUT DIR}/galen-pending`` together with a
``pending.json`` manifest. ``python -m GalenLibrary.approve`` copies them over the baselines.
"""

import json
import os
import shutil
from typing import Optional

MANIFEST = "pending.json"

# One registry per pending folder, shared by all library instances of a run.
_REGISTRIES: dict = {}


class PendingBaselines:
    def __init__(self, root: str):
        self.root = root
        self.entries: dict = {}
        shutil.rmtree(root, ignore_errors=True)

    @classmethod
    def for_root(cls, root: str) -> "PendingBaselines":
        root = os.path.abspath(root)
        if root not in _REGISTRIES:
            _REGISTRIES[root] = cls(root)
        return _REGISTRIES[root]

    def path_for(self, baseline_root: str, baseline: str) -> str:
        """Where the new screenshot for ``baseline`` goes (same layout as the baseline folder)."""
        return os.path.join(self.root, os.path.relpath(baseline, baseline_root))

    def owner(self, baseline_root: str, baseline: str) -> Optional[str]:
        """Test that already kept a screenshot for ``baseline`` (``""`` outside tests), or None."""
        entry = self.entries.get(self.path_for(baseline_root, baseline))
        return None if entry is None else entry["test"] or ""

    def add(
        self, baseline_root: str, baseline: str, reason: str, test: Optional[str], source=None
    ) -> Optional[str]:
        """Registers a new screenshot for ``baseline``; copies ``source`` when given.

        The first failing test wins: later tests often change the page on purpose, so their
        screenshot is not a good candidate. Returns None when an earlier one is kept.
        """
        target = self.path_for(baseline_root, baseline)
        if target in self.entries:
            return None
        if source:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(source, target)
        relative = os.path.relpath(baseline, baseline_root).replace(os.sep, "/")
        self.entries[target] = {
            "pending": os.path.relpath(target, self.root).replace(os.sep, "/"),
            "baseline": relative,
            "baseline_root": os.path.abspath(baseline_root),
            "reason": reason,
            "test": test,
        }
        self._write()
        return target

    def discard(self, targets) -> None:
        """Forgets screenshots of tests that passed after all (e.g. an expected error)."""
        for target in targets:
            if self.entries.pop(target, None) is not None and os.path.isfile(target):
                os.remove(target)
                self._remove_empty_folders(os.path.dirname(target))
        self._write()

    def _remove_empty_folders(self, folder: str) -> None:
        while (
            os.path.normcase(folder).startswith(os.path.normcase(self.root)) and folder != self.root
        ):
            if os.listdir(folder):
                return
            os.rmdir(folder)
            folder = os.path.dirname(folder)

    def _write(self) -> None:
        manifest = os.path.join(self.root, MANIFEST)
        if not self.entries:
            if os.path.isfile(manifest):
                os.remove(manifest)
            return
        os.makedirs(self.root, exist_ok=True)
        with open(manifest, "w", encoding="utf-8") as f:
            json.dump({"files": list(self.entries.values())}, f, indent=2)


def read_manifest(path: str) -> tuple:
    """Returns ``(pending_root, entries)`` for an output folder or a ``galen-pending`` folder."""
    for root in (os.path.join(path, "galen-pending"), path):
        manifest = os.path.join(root, MANIFEST)
        if os.path.isfile(manifest):
            with open(manifest, encoding="utf-8") as f:
                return root, json.load(f)["files"]
    return None, []
