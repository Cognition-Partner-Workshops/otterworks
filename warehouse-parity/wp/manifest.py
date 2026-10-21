"""Object manifest: what exists in the legacy estate, how to run it, how to compare it."""
import glob
import os
from pathlib import Path

import yaml


def find(path=None):
    path = path or os.environ.get("WP_MANIFEST")
    if path:
        return Path(path).resolve()
    root = Path(__file__).resolve().parents[2]
    hits = sorted(glob.glob(str(root / "**" / "azure-synapse" / "manifest.yaml"), recursive=True))
    if not hits:
        raise SystemExit("No manifest found. Pass --manifest or set WP_MANIFEST.")
    return Path(hits[0])


class Manifest:
    def __init__(self, path=None):
        self.path = find(path)
        self.root = self.path.parent
        self.data = yaml.safe_load(self.path.read_text())
        self.objects = {o["name"].lower(): o for o in self.data["objects"]}

    def obj(self, name):
        try:
            return self.objects[name.lower()]
        except KeyError:
            raise SystemExit(f"{name} is not in {self.path}. Known: {', '.join(self.objects)}")

    def wave(self, n):
        return [o for o in self.data["objects"] if o.get("wave") == n]

    def file(self, rel):
        return self.root / rel
