"""Shared paths and settings for the LeadTube Python tools.

Folder layout (project root = the folder above this one):
    .env          API keys (private)
    data/         the tool's memory and your dashboard settings
    results/      Search 01.csv, Search 02.csv ..., all_channels.csv
    ICP.md        who you are looking for (search phrases, roles, topics, exclusions)
    finder/       this code
"""

import os
import re
from pathlib import Path

FINDER_DIR = Path(__file__).resolve().parent
# LEADTUBE_ROOT points the tools at another project folder (used for safe test runs).
ROOT = Path(os.environ["LEADTUBE_ROOT"]).resolve() if os.environ.get("LEADTUBE_ROOT") else FINDER_DIR.parent
ENV_FILE = ROOT / ".env"
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"


def read_env():
    """KEY=value pairs from .env (real environment variables win)."""
    values = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    for key in list(values):
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def env(key, default=""):
    return os.environ.get(key) or read_env().get(key, default)


def set_env(key, value):
    """Write one key to .env, keeping the rest of the file (comments included)."""
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    for i, line in enumerate(lines):
        if pattern.match(line):
            lines[i] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n")
    ENV_FILE.chmod(0o600)
