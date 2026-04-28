#!/usr/bin/env python3
"""Extract Patrick's Parabox demo level layouts from Unity asset strings."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_ASSET = Path(
    "~/Library/Application Support/Steam/steamapps/common/"
    "Patrick's Parabox Demo/Patrick's Parabox.app/Contents/Resources/Data/resources.assets"
).expanduser()

OBJECT_PREFIXES = ("Block ", "Wall ", "Floor ", "Ref ")
NOISE_NAMES = {
    "resources.assets.resS",
    "achievement_groups",
}


@dataclass
class Level:
    name: str
    version: str
    lines: list[str]
    start_line: int
    blocks: list["Block"] = field(default_factory=list)


@dataclass
class Block:
    x: int
    y: int
    block_id: int
    width: int
    height: int
    color: tuple[float, float, float]
    flags: tuple[int, ...]
    raw: str
    parent_id: int | None = None
    objects: list[str] = field(default_factory=list)

    @property
    def is_player(self) -> bool:
        return self.flags[:3] == (1, 1, 1)


def asset_strings(path: Path) -> list[str]:
    data = path.read_bytes()
    runs: list[str] = []
    current = bytearray()
    for byte in data:
        if byte in (9, 10, 13) or 32 <= byte <= 126:
            current.append(byte)
            continue
        if current:
            runs.append(current.decode("utf-8", errors="replace"))
            current.clear()
    if current:
        runs.append(current.decode("utf-8", errors="replace"))

    lines: list[str] = []
    for run in runs:
        lines.extend(run.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
    return lines


def looks_like_name(line: str) -> bool:
    value = line.strip()
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value)) and value not in NOISE_NAMES


def parse_levels(lines: list[str]) -> list[Level]:
    known_names = parse_level_properties(lines)
    levels: list[Level] = []
    for i, line in enumerate(lines):
        if not line.startswith("version "):
            continue
        name = nearest_level_name(lines, i, known_names)
        if name is None:
            continue

        body: list[str] = []
        k = i + 1
        while k < len(lines):
            cur = lines[k]
            stripped = cur.lstrip("\t")
            if cur.startswith("version "):
                break
            if stripped.startswith(OBJECT_PREFIXES) or stripped == "#":
                body.append(cur)
                k += 1
                continue
            if body and looks_like_name(stripped):
                break
            if body and stripped.strip() == "":
                k += 1
                continue
            if body and not stripped.startswith(OBJECT_PREFIXES):
                break
            k += 1

        object_lines = [item for item in body if item.lstrip("\t") != "#"]
        if any(item.lstrip("\t").startswith(OBJECT_PREFIXES) for item in object_lines):
            level = Level(name, line.strip(), object_lines, i + 1)
            parse_blocks(level)
            levels.append(level)
    return levels


def parse_level_properties(lines: list[str]) -> set[str]:
    names: set[str] = {"hub"}
    pattern = re.compile(r"^([a-z][a-z0-9_]*)\s+-?\d+\s+-?\d+\s+-?\d+\s+-?\d+\s+-?\d+\s+[ab]\d+$")
    for line in lines:
        match = pattern.match(line)
        if match:
            names.add(match.group(1))
    return names


def nearest_level_name(lines: list[str], version_index: int, known_names: set[str]) -> str | None:
    candidates: list[str] = []
    for j in range(version_index - 1, max(-1, version_index - 8), -1):
        value = lines[j].strip()
        if not value:
            continue
        if value in known_names:
            return value
        candidates.append(value)

    for value in candidates:
        for known in sorted(known_names, key=len, reverse=True):
            if value.startswith(known):
                return known

    for value in candidates:
        if looks_like_name(value):
            return value
    return None


def parse_blocks(level: Level) -> None:
    stack: list[Block] = []
    for line in level.lines:
        stripped = line.lstrip("\t")
        depth = len(line) - len(stripped)
        if stripped.startswith("Block "):
            parts = stripped.split()
            if len(parts) >= 6:
                parent = stack[depth - 1].block_id if depth > 0 and depth - 1 < len(stack) else None
                block = Block(
                    x=int(parts[1]),
                    y=int(parts[2]),
                    block_id=int(parts[3]),
                    width=int(parts[4]),
                    height=int(parts[5]),
                    color=(float(parts[6]), float(parts[7]), float(parts[8])),
                    flags=tuple(int(item) for item in parts[10:]),
                    raw=stripped,
                    parent_id=parent,
                )
                level.blocks.append(block)
                del stack[depth:]
                stack.append(block)
            continue
        if depth > 0 and depth - 1 < len(stack):
            stack[depth - 1].objects.append(stripped)


def frame_y(block: Block, y: int, coords: str) -> int:
    return block.height - 1 - y if coords == "screen" else y


def render_block_parts(block: Block, coords: str = "screen") -> tuple[list[list[str]], list[str]]:
    grid = [["." for _ in range(block.width)] for _ in range(block.height)]
    labels: list[str] = []

    for line in block.objects:
        parts = line.split()
        if len(parts) < 3:
            continue
        kind = parts[0]
        try:
            x = int(parts[1])
            y = int(parts[2])
        except ValueError:
            continue
        if not (0 <= x < block.width and 0 <= y < block.height):
            continue
        out_y = frame_y(block, y, coords)

        char = {
            "Wall": "#",
            "Ref": "R",
        }.get(kind, "?")
        if kind == "Floor":
            floor_kind = parts[3] if len(parts) > 3 else "Floor"
            char = {
                "Button": "b",
                "PlayerButton": "p",
                "Portal": "P",
                "DemoEnd": "E",
            }.get(floor_kind, "f")
            if floor_kind == "Portal" and len(parts) > 4:
                labels.append(f"P ({x},{out_y}) -> {parts[4]}")
            elif floor_kind:
                labels.append(f"{char} ({x},{out_y}) {floor_kind}")
        if kind == "Ref" and len(parts) > 16:
            labels.append(f"R ({x},{out_y}) {parts[-1]}")
        grid[out_y][x] = char

    # Child blocks are parsed as separate block records. This renderer is
    # intentionally local, so callers overlay them after parse_blocks().

    return grid, labels


def render_block(block: Block, coords: str = "screen") -> str:
    grid, labels = render_block_parts(block, coords)
    rendered = "\n".join("".join(row) for row in grid)
    if labels:
        rendered += "\n" + "\n".join(labels)
    return rendered


def render_level_block(level: Level, block_index: int, coords: str = "screen") -> str:
    block = level.blocks[block_index]
    grid, labels = render_block_parts(block, coords)
    for index, child in enumerate(level.blocks):
        if index == block_index:
            continue
        if child.parent_id != block.block_id:
            continue
        if not (0 <= child.x < block.width and 0 <= child.y < block.height):
            continue
        out_y = frame_y(block, child.y, coords)
        char = "@" if child.is_player else str(child.block_id % 10)
        existing = grid[out_y][child.x]
        if existing == ".":
            grid[out_y][child.x] = char
        else:
            grid[out_y][child.x] = char.lower()
        if child.is_player:
            labels.append(
                f"{char} initial_cell=({child.x},{out_y}) controlled-player id={child.block_id} "
                f"footprint=1x1 inner_size={child.width}x{child.height} enterable=no pushable=no"
            )
        else:
            labels.append(
                f"{char} initial_cell=({child.x},{out_y}) block id={child.block_id} "
                f"footprint=1x1 inner_size={child.width}x{child.height}"
            )
    return "\n".join("".join(row) for row in grid) + ("\n" + "\n".join(labels) if labels else "")


def find_level(levels: list[Level], name: str) -> Level:
    matches = [level for level in levels if level.name == name]
    if not matches:
        available = ", ".join(level.name for level in levels)
        raise SystemExit(f"Unknown level '{name}'. Available levels: {available}")
    if len(matches) > 1:
        print(f"warning: {len(matches)} chunks named {name}; showing the first")
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", type=Path, default=DEFAULT_ASSET)
    parser.add_argument("--list", action="store_true", help="List extracted level chunks")
    parser.add_argument("--level", help="Level name to print")
    parser.add_argument("--raw", action="store_true", help="Print raw object lines")
    parser.add_argument("--block", type=int, default=0, help="Block index to render")
    parser.add_argument(
        "--coords",
        choices=["screen", "raw"],
        default="screen",
        help="Coordinate frame for rendered grids and labels. screen is public/default.",
    )
    args = parser.parse_args()

    levels = parse_levels(asset_strings(args.asset.expanduser()))
    if args.list or not args.level:
        for index, level in enumerate(levels):
            dims = ", ".join(f"{b.block_id}:{b.width}x{b.height}@{b.x},{b.y}" for b in level.blocks[:4])
            extra = " ..." if len(level.blocks) > 4 else ""
            print(f"{index:02d} {level.name} ({len(level.blocks)} blocks) {dims}{extra}")
        if not args.level:
            return 0

    level = find_level(levels, args.level)
    print(f"level={level.name}")
    print(f"{level.version} asset_line={level.start_line}")
    print(f"blocks={len(level.blocks)}")
    print("note=colors are visual only; use read_patrick_blocks.py for enterable/pushable interaction")
    print("note=block pos is one cell in its parent board; inner_size is not outer footprint")
    for index, block in enumerate(level.blocks):
        if block.parent_id is None:
            role = "level-root"
            footprint = "-"
        elif block.is_player:
            role = "controlled-player"
            footprint = "1x1"
        else:
            role = "block"
            footprint = "1x1"
        color = ",".join(f"{item:g}" for item in block.color)
        print(
            f"block[{index}] id={block.block_id} cell=({block.x},{block.y}) "
            f"footprint={footprint} inner_size={block.width}x{block.height} parent={block.parent_id} "
            f"color={color} role={role}"
        )

    if args.raw:
        print("raw:")
        print("\n".join(level.lines))

    if not level.blocks:
        return 0
    if not (0 <= args.block < len(level.blocks)):
        raise SystemExit(f"--block must be between 0 and {len(level.blocks) - 1}")
    print(f"render block[{args.block}] coords={args.coords}:")
    print(render_level_block(level, args.block, args.coords))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
