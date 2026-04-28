#!/usr/bin/env python3
"""Read the latest patched Patrick state line from Unity's Player.log."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from patrick_coords import Coord, CoordFrame, frame_for_level
from read_patrick_levels import DEFAULT_ASSET


DEFAULT_LOG = Path("~/Library/Logs/Patrick Traynor/Patrick's Parabox/Player.log").expanduser()
STATE_RE = re.compile(
    r"^(?P<level>[A-Za-z0-9_]+)"
    r"(?:/(?P<area>[A-Za-z0-9_]*))?"
    r"(?:/(?P<state>[A-Za-z0-9_]+))?"
    r" (?P<x>-?\d+) (?P<y>-?\d+)$"
)
PROBE_RE = re.compile(
    r"^(?P<state>Initializing|Playing|Paused|Credits|Break|Show|FastTravel|Gallery)"
    r" (?P<x>-?\d+) (?P<y>-?\d+)$"
)


def latest_state(path: Path) -> tuple[str, str, str, int, int] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()
    for line in reversed(lines[-5000:]):
        stripped = line.strip()
        match = PROBE_RE.match(stripped)
        if match:
            return (
                "",
                "",
                match.group("state"),
                int(match.group("x")),
                int(match.group("y")),
            )
        match = STATE_RE.match(stripped)
        if match:
            level = match.group("level")
            if level.lstrip("-").isdigit():
                continue
            return (
                level,
                match.group("area") or "",
                match.group("state") or "",
                int(match.group("x")),
                int(match.group("y")),
            )
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument(
        "--coords",
        choices=["raw", "screen", "both"],
        default="screen",
        help="Coordinate frame to print. screen is the public/default frame: up is y-1 and down is y+1.",
    )
    parser.add_argument("--height", type=int, help="Board height for screen coordinate conversion")
    parser.add_argument("--level", help="Level name used to discover board height")
    parser.add_argument("--block", type=int, help="Level block index used with --level")
    parser.add_argument("--asset", type=Path, default=DEFAULT_ASSET)
    args = parser.parse_args()

    state = latest_state(args.log.expanduser())
    if state is None:
        print("state=not-found")
        return 1
    level, area, world_state, x, y = state
    print(f"level={level}")
    print(f"area={area}")
    print(f"state={world_state}")

    frame: CoordFrame | None = None
    if args.coords in {"screen", "both"}:
        if args.height is not None:
            frame = CoordFrame(width=0, height=args.height)
        else:
            level_for_height = args.level or level
            if level_for_height:
                frame = frame_for_level(args.asset, level_for_height, args.block)

    raw = Coord(x, y)
    if args.coords == "raw" or frame is None:
        if args.coords in {"screen", "both"}:
            print("coords=raw")
            print("screen_unavailable=missing-level-or-height")
        else:
            print("coords=raw")
        print(f"x={raw.x}")
        print(f"y={raw.y}")
    elif args.coords == "screen":
        screen = frame.to_screen(raw)
        print("coords=screen")
        print(f"x={screen.x}")
        print(f"y={screen.y}")
        print(f"raw_x={raw.x}")
        print(f"raw_y={raw.y}")
        print(f"height={frame.height}")
    else:
        screen = frame.to_screen(raw)
        print("coords=both")
        print(f"raw_x={raw.x}")
        print(f"raw_y={raw.y}")
        print(f"screen_x={screen.x}")
        print(f"screen_y={screen.y}")
        print(f"height={frame.height}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
