#!/usr/bin/env python3
"""List Patrick's Parabox blocks that can be entered versus only pushed."""

from __future__ import annotations

import argparse
from pathlib import Path

from read_patrick_levels import DEFAULT_ASSET, Block, asset_strings, find_level, frame_y, parse_levels


def wall_cells(block: Block) -> set[tuple[int, int]]:
    walls: set[tuple[int, int]] = set()
    for line in block.objects:
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "Wall":
            try:
                walls.add((int(parts[1]), int(parts[2])))
            except ValueError:
                continue
    return walls


def opening_edges(block: Block, coords: str) -> list[str]:
    walls = wall_cells(block)
    if block.width <= 0 or block.height <= 0:
        return []

    edges: list[str] = []
    if any((x, block.height - 1) not in walls for x in range(block.width)):
        edges.append("up" if coords == "screen" else "down")
    if any((x, 0) not in walls for x in range(block.width)):
        edges.append("down" if coords == "screen" else "up")
    if any((0, y) not in walls for y in range(block.height)):
        edges.append("left")
    if any((block.width - 1, y) not in walls for y in range(block.height)):
        edges.append("right")
    return edges


def block_role(block: Block) -> str:
    return "controlled-player" if block.is_player else "block"


def interaction(block: Block) -> tuple[str, bool, bool, str]:
    if block.is_player:
        return "controlled-player", False, False, "current-player-not-a-target"
    edges = opening_edges(block, "screen")
    if edges:
        return "enterable", True, True, "has-open-edge"
    return "push-only", False, True, "sealed-block"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", type=Path, default=DEFAULT_ASSET)
    parser.add_argument("--level", required=True)
    parser.add_argument(
        "--coords",
        choices=["screen", "raw"],
        default="screen",
        help="Coordinate frame for block positions and openings. screen is public/default.",
    )
    parser.add_argument(
        "--parent-id",
        type=int,
        help="Only show blocks inside this parent block id. By default, show all non-root blocks.",
    )
    args = parser.parse_args()

    level = find_level(parse_levels(asset_strings(args.asset.expanduser())), args.level)
    parents = {block.block_id: block for block in level.blocks}

    print(f"level={level.name}")
    print(f"coords={args.coords}")
    print("note=do-not-infer-interaction-from-color; use interaction/enterable/pushable")
    print("note=initial_cell is one cell in the parent board; inner_size is not outer footprint")
    print("note=use read_patrick_state_log.py for current player position before every key")
    print("note=use read_patrick_live_blocks.py for current non-player cells after installing --live-blocks")
    for index, block in enumerate(level.blocks):
        if block.parent_id is None:
            continue
        if args.parent_id is not None and block.parent_id != args.parent_id:
            continue
        parent = parents.get(block.parent_id)
        y = frame_y(parent, block.y, args.coords) if parent is not None else block.y
        role = block_role(block)
        kind, enterable, pushable, note = interaction(block)
        edges = opening_edges(block, args.coords) if kind == "enterable" else []
        edge_text = ",".join(edges) if edges else "-"
        print(
            f"block[{index}] id={block.block_id}\tparent={block.parent_id}\trole={role}\t"
            f"interaction={kind}\tenterable={'yes' if enterable else 'no'}\t"
            f"pushable={'yes' if pushable else 'no'}\tinitial_cell=({block.x},{y})\t"
            f"footprint=1x1\tinner_size={block.width}x{block.height}\t"
            f"openings={edge_text}\tnote={note}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
