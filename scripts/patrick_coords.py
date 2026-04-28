#!/usr/bin/env python3
"""Coordinate helpers for Patrick's Parabox tooling.

The game data uses a top-left origin for level layouts, but the key events we
observe from Unity are easiest to reason about after flipping the y axis.  This
module keeps both frames explicit:

raw:    coordinates as stored/logged by the game.
screen: public/default coordinates with y flipped so up/down match visible movement.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from read_patrick_levels import DEFAULT_ASSET, asset_strings, find_level, parse_levels


@dataclass(frozen=True)
class Coord:
    x: int
    y: int


@dataclass(frozen=True)
class CoordFrame:
    width: int
    height: int

    def to_screen(self, raw: Coord) -> Coord:
        return Coord(raw.x, self.height - 1 - raw.y)

    def to_raw(self, screen: Coord) -> Coord:
        return Coord(screen.x, self.height - 1 - screen.y)


def frame_for_level(asset: Path, level_name: str, block_index: int | None = None) -> CoordFrame:
    levels = parse_levels(asset_strings(asset.expanduser()))
    level = find_level(levels, level_name)
    if not level.blocks:
        raise SystemExit(f"Level has no blocks: {level_name}")
    if block_index is None:
        # The demo hub's playable intro area is block[3]. Normal puzzle levels
        # use block[0] as their root board.
        block_index = 3 if level.name == "hub" and len(level.blocks) > 3 else 0
    if not (0 <= block_index < len(level.blocks)):
        raise SystemExit(f"--block must be between 0 and {len(level.blocks) - 1}")
    block = level.blocks[block_index]
    return CoordFrame(block.width, block.height)


def key_for_screen_move(move: str) -> str:
    """Return the reliable input key for a natural screen-space move."""

    keys = {
        "up": "up",
        "down": "down",
        "left": "left",
        # The right arrow did not reliably move in the current desktop session;
        # WASD 'd' has been reliable.
        "right": "d",
    }
    try:
        return keys[move]
    except KeyError as exc:
        valid = ", ".join(sorted(keys))
        raise SystemExit(f"Unknown screen move '{move}'. Valid moves: {valid}") from exc


def screen_move_for_raw_move(move: str) -> str:
    """Convert a solver/raw move name to the corresponding screen move name."""

    moves = {
        "up": "down",
        "down": "up",
        "left": "left",
        "right": "right",
    }
    try:
        return moves[move]
    except KeyError as exc:
        valid = ", ".join(sorted(moves))
        raise SystemExit(f"Unknown raw move '{move}'. Valid moves: {valid}") from exc


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("x", type=int)
    parser.add_argument("y", type=int)
    parser.add_argument("--asset", type=Path, default=DEFAULT_ASSET)
    parser.add_argument("--level", required=True)
    parser.add_argument("--block", type=int)
    parser.add_argument("--from", dest="source", choices=["raw", "screen"], default="raw")
    args = parser.parse_args()

    frame = frame_for_level(args.asset, args.level, args.block)
    coord = Coord(args.x, args.y)
    other = frame.to_screen(coord) if args.source == "raw" else frame.to_raw(coord)
    print(f"frame={frame.width}x{frame.height}")
    print(f"{args.source}=({coord.x},{coord.y})")
    target = "screen" if args.source == "raw" else "raw"
    print(f"{target}=({other.x},{other.y})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
