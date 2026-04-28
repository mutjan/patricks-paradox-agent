#!/usr/bin/env python3
"""List Patrick's Parabox demo hub portals and save-derived status."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from read_patrick_levels import DEFAULT_ASSET, Block, asset_strings, find_level, frame_y, parse_levels


DEFAULT_SAVE_DIR = Path("~/Library/Application Support/com.PatrickTraynor.PatricksParabox").expanduser()


@dataclass(frozen=True)
class SaveLevel:
    unlocked: bool | None
    completed: bool


@dataclass(frozen=True)
class Portal:
    area: str
    refs: str
    start_area: bool
    block_id: int
    x: int
    y: int
    target: str
    locked_by: str | None


def default_save_path(slot: int) -> Path:
    return DEFAULT_SAVE_DIR / f"save_demo{slot}.txt"


def find_save(slot: int) -> Path | None:
    preferred = default_save_path(slot)
    if preferred.exists():
        return preferred
    candidates = sorted(DEFAULT_SAVE_DIR.glob("save_demo*.txt"))
    return candidates[0] if candidates else None


def parse_save(path: Path | None) -> dict[str, SaveLevel]:
    if path is None or not path.exists():
        return {}

    levels: dict[str, SaveLevel] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            continue
        values: list[int] = []
        for item in parts[1:]:
            try:
                values.append(int(item))
            except ValueError:
                break
        if not values:
            continue
        if len(values) >= 2:
            levels[parts[0]] = SaveLevel(unlocked=values[0] != 0, completed=values[1] != 0)
        else:
            levels[parts[0]] = SaveLevel(unlocked=None, completed=values[0] != 0)
    return levels


def ref_labels(block: Block) -> list[str]:
    labels: list[str] = []
    for line in block.objects:
        parts = line.split()
        if len(parts) >= 4 and parts[0] == "Ref":
            label = parts[-1]
            if label and label != "_":
                labels.append(label)
    return labels


def named_walls(block: Block) -> list[str]:
    names: list[str] = []
    for line in block.objects:
        parts = line.split()
        if len(parts) >= 6 and parts[0] == "Wall":
            label = parts[-1]
            if label and label != "_" and not label.lstrip("-").isdigit():
                names.append(label)
    return names


def infer_area_locks(blocks: list[Block]) -> dict[int, str]:
    locks: dict[int, str] = {}
    by_id = {block.block_id: block for block in blocks}
    for block in blocks:
        names = named_walls(block)
        if not names:
            continue
        for line in block.objects:
            parts = line.split()
            if len(parts) < 4 or parts[0] != "Ref":
                continue
            try:
                target_id = int(parts[3])
            except ValueError:
                continue
            if target_id in by_id:
                locks[target_id] = ",".join(dict.fromkeys(names))
    return locks


def hub_portals(asset: Path, coords: str) -> list[Portal]:
    hub = find_level(parse_levels(asset_strings(asset.expanduser())), "hub")
    area_locks = infer_area_locks(hub.blocks)
    player_parent_ids = {block.parent_id for block in hub.blocks if block.is_player and block.parent_id is not None}
    portals: list[Portal] = []
    for block in hub.blocks:
        area = f"hub_block_{block.block_id}"
        refs = ",".join(ref_labels(block)) or "-"
        start_area = block.block_id in player_parent_ids
        locked_by = area_locks.get(block.block_id)
        for line in block.objects:
            parts = line.split()
            if len(parts) < 5 or parts[0] != "Floor" or parts[3] != "Portal":
                continue
            x = int(parts[1])
            y = frame_y(block, int(parts[2]), coords)
            portals.append(Portal(area, refs, start_area, block.block_id, x, y, parts[4], locked_by))
    return sorted(portals, key=lambda item: (not item.start_area, item.block_id, item.y, item.x, item.target))


def portal_status(portal: Portal, save_levels: dict[str, SaveLevel]) -> tuple[str, str]:
    target = save_levels.get(portal.target)
    if target is not None and target.completed:
        return "completed", "-"
    if portal.locked_by:
        blockers = [name for name in portal.locked_by.split(",") if name]
        unsolved = [name for name in blockers if not save_levels.get(name, SaveLevel(None, False)).completed]
        if unsolved:
            return "locked", ",".join(unsolved)
    if target is not None and target.unlocked is False:
        return "locked", "save"
    return "enterable", "-"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", type=Path, default=DEFAULT_ASSET)
    parser.add_argument("--save", type=Path, help="Path to save_demoN.txt")
    parser.add_argument("--slot", type=int, default=0, help="Save slot used when --save is omitted")
    parser.add_argument(
        "--coords",
        choices=["screen", "raw"],
        default="screen",
        help="Coordinate frame for portal positions. screen is public/default.",
    )
    args = parser.parse_args()

    save_path = args.save.expanduser() if args.save else find_save(args.slot)
    save_levels = parse_save(save_path)
    print(f"coords={args.coords}")
    if save_path is None:
        print("save=not-found")
        print("note=Patrick's Parabox normally creates save_demoN.txt after at least one level is completed")
    else:
        print(f"save={save_path}")

    last_area: str | None = None
    for portal in hub_portals(args.asset, args.coords):
        if portal.area != last_area:
            lock = portal.locked_by or "-"
            start = "yes" if portal.start_area else "no"
            print(f"area={portal.area} block_id={portal.block_id} start={start} locked_by={lock} ref_labels={portal.refs}")
            last_area = portal.area
        status, locked_by = portal_status(portal, save_levels)
        print(f"{portal.target}\tstatus={status}\tpos=({portal.x},{portal.y})\tlocked_by={locked_by}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
