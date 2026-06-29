#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["ruamel.yaml>=0.18"]
# ///
"""Reconcile repo-owned config keys onto the live profile config.yaml.

Deep-merges ``config.overrides.yaml`` onto the profile's ``config.yaml``,
preserving every other key, comment, and formatting detail (ruamel round-trip).
Idempotent: prints ``changed`` (and rewrites the file) or ``nochange``.

This is GitOps for config. The repo owns the keys in the overrides file; the
deploy enforces them, so a config change ships via ``git push``, not SSH.

Usage: apply_config_overrides.py <overrides.yaml> <live-config.yaml>
"""
import io
import sys
from pathlib import Path

from ruamel.yaml import YAML


def deep_merge(base: dict, over: dict) -> None:
    """Recursively set over's keys into base; non-dict values overwrite."""
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: apply_config_overrides.py <overrides.yaml> <config.yaml>", file=sys.stderr)
        return 2
    overrides_path, config_path = Path(sys.argv[1]), Path(sys.argv[2])

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # never line-wrap values

    overrides = yaml.load(overrides_path.read_text()) or {}
    original = config_path.read_text()
    config = yaml.load(original)
    deep_merge(config, overrides)

    buf = io.StringIO()
    yaml.dump(config, buf)
    rendered = buf.getvalue()

    if rendered == original:
        print("nochange")
        return 0
    config_path.write_text(rendered)
    print("changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
