#!/usr/bin/env python3
"""Toggle an OpenTelemetry Demo flagd flag to inject or clear a fault.

Usage: python scenarios/inject.py <demo_dir> <flag_key> <on|off>

flagd watches its config file and hot-reloads, so the fault takes effect (or clears)
without restarting anything. This is the same edit FlagActuator makes to remediate.
"""
import json
import os
import sys


def toggle(demo_dir: str, flag: str, variant: str) -> str:
    path = os.path.join(demo_dir, "src", "flagd", "demo.flagd.json")
    with open(path) as f:
        cfg = json.load(f)
    if flag not in cfg["flags"]:
        raise SystemExit(f"unknown flag '{flag}'; see {path}")
    cfg["flags"][flag]["defaultVariant"] = variant
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, path)
    return path


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[3] not in ("on", "off"):
        raise SystemExit("usage: inject.py <demo_dir> <flag_key> <on|off>")
    p = toggle(sys.argv[1], sys.argv[2], sys.argv[3])
    print(f"{sys.argv[2]} -> {sys.argv[3]} ({p})")
