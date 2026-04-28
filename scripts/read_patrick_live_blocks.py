#!/usr/bin/env python3
"""Read live non-player block cells from the patched Unity Player.log."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from patrick_coords import Coord, CoordFrame, frame_for_level
from read_patrick_levels import DEFAULT_ASSET
from read_patrick_state_log import DEFAULT_LOG, PROBE_RE, STATE_RE


BLOCK_RE = re.compile(r"^(?P<id>-?\d+) (?P<x>-?\d+) (?P<y>-?\d+)$")


@dataclass(frozen=True)
class LoggedState:
    level: str
    area: str
    state: str
    x: int
    y: int


@dataclass(frozen=True)
class LoggedBlock:
    block_id: int
    x: int
    y: int


def parse_state(line: str) -> LoggedState | None:
    probe = PROBE_RE.match(line)
    if probe:
        return LoggedState(
            level="",
            area="",
            state=probe.group("state"),
            x=int(probe.group("x")),
            y=int(probe.group("y")),
        )
    state = STATE_RE.match(line)
    if state:
        level = state.group("level")
        if level.lstrip("-").isdigit():
            return None
        return LoggedState(
            level=level,
            area=state.group("area") or "",
            state=state.group("state") or "",
            x=int(state.group("x")),
            y=int(state.group("y")),
        )
    return None


def latest_frame(path: Path) -> tuple[LoggedState, list[LoggedBlock]] | None:
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8", errors="replace") as fh:
        lines = [line.strip() for line in fh.readlines()[-10000:]]

    for index in range(len(lines) - 1, -1, -1):
        state = parse_state(lines[index])
        if state is None:
            continue

        blocks: list[LoggedBlock] = []
        for line in lines[index + 1 :]:
            if parse_state(line) is not None:
                break
            match = BLOCK_RE.match(line)
            if match:
                blocks.append(
                    LoggedBlock(
                        block_id=int(match.group("id")),
                        x=int(match.group("x")),
                        y=int(match.group("y")),
                    )
                )
                continue
            if line:
                break
        return state, blocks

    return None


def convert(coord: Coord, frame: CoordFrame | None) -> Coord:
    return frame.to_screen(coord) if frame is not None else coord


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument(
        "--coords",
        choices=["screen", "raw", "both"],
        default="screen",
        help="Coordinate frame to print. screen is public/default: up is y-1 and down is y+1.",
    )
    parser.add_argument("--height", type=int, help="Board height for screen coordinate conversion")
    parser.add_argument("--level", help="Level name used to discover board height")
    parser.add_argument("--block", type=int, help="Level block index used with --level")
    parser.add_argument("--asset", type=Path, default=DEFAULT_ASSET)
    args = parser.parse_args()

    frame_data = latest_frame(args.log.expanduser())
    if frame_data is None:
        print("state=not-found")
        return 1

    state, blocks = frame_data
    print(f"level={state.level}")
    print(f"area={state.area}")
    print(f"state={state.state}")
    print("scope=current-player-outer-board")
    print("note=block id is runtime DebugID; match to asset blocks by cell/interaction, not by asset id")
    print("note=static walls are not live-logged; use read_patrick_levels.py for walls and initial terrain")

    frame: CoordFrame | None = None
    if args.coords in {"screen", "both"}:
        if args.height is not None:
            frame = CoordFrame(width=0, height=args.height)
        else:
            level_for_height = args.level or state.level
            if level_for_height:
                frame = frame_for_level(args.asset, level_for_height, args.block)

    raw_player = Coord(state.x, state.y)
    screen_player = convert(raw_player, frame)

    if args.coords == "raw" or frame is None:
        if args.coords in {"screen", "both"}:
            print("coords=raw")
            print("screen_unavailable=missing-level-or-height")
        else:
            print("coords=raw")
        print(f"player_x={raw_player.x}")
        print(f"player_y={raw_player.y}")
    elif args.coords == "screen":
        print("coords=screen")
        print(f"player_x={screen_player.x}")
        print(f"player_y={screen_player.y}")
        print(f"player_raw_x={raw_player.x}")
        print(f"player_raw_y={raw_player.y}")
        print(f"height={frame.height}")
    else:
        print("coords=both")
        print(f"player_raw_x={raw_player.x}")
        print(f"player_raw_y={raw_player.y}")
        print(f"player_screen_x={screen_player.x}")
        print(f"player_screen_y={screen_player.y}")
        print(f"height={frame.height}")

    print(f"blocks={len(blocks)}")
    if not blocks:
        print("note=no non-player block lines after latest state; this can also mean the old position-only patch is installed")

    for block in blocks:
        raw = Coord(block.x, block.y)
        screen = convert(raw, frame)
        if args.coords == "raw" or frame is None:
            print(f"block id={block.block_id}\tx={raw.x}\ty={raw.y}")
        elif args.coords == "screen":
            print(
                f"block id={block.block_id}\tx={screen.x}\ty={screen.y}\t"
                f"raw_x={raw.x}\traw_y={raw.y}"
            )
        else:
            print(
                f"block id={block.block_id}\traw_x={raw.x}\traw_y={raw.y}\t"
                f"screen_x={screen.x}\tscreen_y={screen.y}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
