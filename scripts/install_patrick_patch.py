#!/usr/bin/env python3
"""Install, inspect, or restore the Patrick state/logger patch."""

from __future__ import annotations

import argparse
from pathlib import Path

import inspect_dotnet_metadata as meta
import patch_patrick_state_logger as logger


def backup_path(assembly: Path) -> Path:
    return assembly.with_name(assembly.name + logger.BACKUP_SUFFIX)


def method_il(assembly: Path, type_name: str, method_name: str) -> bytes:
    data = assembly.read_bytes()
    rva = logger.method_rva(assembly, type_name, method_name)
    return meta.il_bytes(data, rva)


def patch_mode(assembly: Path) -> str:
    code = method_il(assembly, "World", "LateUpdate")
    if code.startswith(logger.build_live_blocks_lateupdate_il()):
        helper = method_il(assembly, "World", "InspectUpdate")
        if helper.startswith(logger.build_live_blocks_helper_il()):
            return "live_blocks"
        return "live_blocks_lateupdate_only"
    if code.startswith(logger.build_position_logger_il()):
        return "position"
    if code.startswith(logger.build_state_probe_il()):
        return "state_probe"
    return "unpatched_or_unknown"


def print_status(assembly: Path) -> int:
    print(f"assembly={assembly}")
    print(f"assembly_exists={int(assembly.exists())}")
    print(f"backup={backup_path(assembly)}")
    print(f"backup_exists={int(backup_path(assembly).exists())}")
    if assembly.exists():
        print(f"patch_mode={patch_mode(assembly)}")
    return 0


def require_assembly(assembly: Path) -> None:
    if not assembly.exists():
        raise SystemExit(
            "Assembly not found: "
            f"{assembly}\n"
            "Pass --assembly /path/to/Assembly-CSharp.dll if the game is installed elsewhere."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--assembly",
        type=Path,
        default=logger.ASSEMBLY,
        help="Path to Patrick's Parabox Assembly-CSharp.dll",
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--install", action="store_true", help="Install the logger patch")
    action.add_argument("--restore", action="store_true", help="Restore the backed-up original assembly")
    action.add_argument("--status", action="store_true", help="Print patch and backup status")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--state-probe",
        action="store_true",
        help="Install a debug patch that logs World.State plus player coordinates",
    )
    mode.add_argument(
        "--live-blocks",
        action="store_true",
        help="Install the public live-state patch: player position plus non-player block cells",
    )
    args = parser.parse_args()

    assembly = args.assembly.expanduser().resolve()
    if args.status:
        return print_status(assembly)

    require_assembly(assembly)
    if args.restore:
        logger.restore(assembly)
    else:
        logger.patch(assembly, state_probe=args.state_probe, live_blocks=args.live_blocks)

    print()
    print("Next steps:")
    print("1. Restart Patrick's Parabox if it is already running.")
    print("2. Start the game. If it opens on the menu, press Enter once.")
    if args.live_blocks:
        print("3. Verify logs with: python3 scripts/read_patrick_live_blocks.py")
    else:
        print("3. Verify logs with: python3 scripts/read_patrick_state_log.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
