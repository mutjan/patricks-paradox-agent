#!/usr/bin/env python3
"""Shared configuration for Patrick's Parabox local tooling."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "patrick_config.json"
EXAMPLE_CONFIG_PATH = PROJECT_ROOT / "patrick_config.example.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "app_name": "Patrick's Parabox",
    "input_delay": 0.07,
}


@dataclass(frozen=True)
class PatrickConfig:
    app_name: str
    input_delay: float
    config_path: Path


def expand_path(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(value))).resolve()


def write_default_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if EXAMPLE_CONFIG_PATH.exists():
        raw = json.loads(EXAMPLE_CONFIG_PATH.read_text(encoding="utf-8"))
    else:
        raw = DEFAULT_CONFIG
    path.write_text(json.dumps({**DEFAULT_CONFIG, **raw}, indent=2) + "\n", encoding="utf-8")


def load_config(path: Path | None = None) -> PatrickConfig:
    raw_path = path if path is not None else Path(os.environ.get("PATRICK_CONFIG", str(DEFAULT_CONFIG_PATH)))
    config_path = expand_path(str(raw_path))
    if not config_path.exists():
        write_default_config(config_path)
        raise SystemExit(
            "Created config file at "
            f"{config_path}.\n"
            "Review it, then rerun the command. Set PATRICK_CONFIG to use a different config file."
        )

    raw: dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))
    merged = {**DEFAULT_CONFIG, **raw}
    input_delay = float(merged["input_delay"])
    if input_delay < 0:
        raise SystemExit("input_delay must be non-negative")
    return PatrickConfig(
        app_name=str(merged["app_name"]),
        input_delay=input_delay,
        config_path=config_path,
    )


def main() -> int:
    config = load_config()
    print(f"config_path={config.config_path}")
    print(f"app_name={config.app_name}")
    print(f"input_delay={config.input_delay}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
