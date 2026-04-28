#!/usr/bin/env python3
"""Patch Patrick's Parabox demo to log live grid state every frame.

The default patch replaces World.LateUpdate with a small player logger:

    "{currentLevelName}/{player.OuterLevel.hubAreaName} {player.xpos} {player.ypos}"

The live-blocks patch additionally repurposes World.InspectUpdate as a helper
that logs the current player line followed by one line for each non-player block
in the same outer level:

    "{block.DebugID} {block.xpos} {block.ypos}"

The lines are emitted via UnityEngine.Debug.Log, so they land in Player.log.
The original DLL is backed up next to the assembly and can be restored with
--restore.
"""

from __future__ import annotations

import argparse
import shutil
import struct
from pathlib import Path

import inspect_dotnet_metadata as meta


ASSEMBLY = meta.DEFAULT_ASSEMBLY
BACKUP_SUFFIX = ".patrick_state_logger.bak"


TOKENS = {
    "fmt": 0x70004EDE,  # "{0} {1} {2}"
    "slash": 0x7000087F,  # "/"
    "state": 0x0400033F,
    "state_enum": 0x02000057,
    "current_level_name": 0x0400036E,
    "world_blocks": 0x04000377,
    "block_outer_level": 0x040001C8,
    "block_sub_level": 0x040001C9,
    "block_xpos": 0x040001CA,
    "block_ypos": 0x040001CB,
    "block_is_player": 0x040001CC,
    "block_debug_id": 0x040001F3,
    "level_hub_area_name": 0x0400026A,
    "world_inspect_update": 0x060001A7,
    "find_player_block": 0x060001BF,
    "int32": 0x01000053,
    "list_block_get_item": 0x0A000019,
    "list_block_count": 0x0A00001A,
    "string_concat_3": 0x0A000071,
    "string_format_3": 0x0A0000F4,
    "debug_log": 0x0A000159,
}


class ILBuilder:
    """Small helper for emitting relative branches without hard-coded offsets."""

    def __init__(self) -> None:
        self.code = bytearray()
        self.labels: dict[str, int] = {}
        self.patches: list[tuple[int, str]] = []

    def raw(self, data: bytes) -> None:
        self.code += data

    def emit(self, *values: int) -> None:
        self.code += bytes(values)

    def token(self, opcode: int, token: int) -> None:
        self.raw(emit_token(opcode, token))

    def mark(self, label: str) -> None:
        self.labels[label] = len(self.code)

    def branch(self, opcode: int, label: str) -> None:
        self.emit(opcode)
        operand_offset = len(self.code)
        self.code += b"\x00\x00\x00\x00"
        self.patches.append((operand_offset, label))

    def finish(self) -> bytes:
        for operand_offset, label in self.patches:
            if label not in self.labels:
                raise ValueError(f"Missing IL label: {label}")
            delta = self.labels[label] - (operand_offset + 4)
            self.code[operand_offset : operand_offset + 4] = struct.pack("<i", delta)
        return bytes(self.code)


def emit_token(opcode: int, token: int) -> bytes:
    return bytes([opcode]) + struct.pack("<I", token)


def build_position_logger_il(*, include_ret: bool = True) -> bytes:
    il = bytearray()
    il += emit_token(0x72, TOKENS["fmt"])  # ldstr "{0} {1} {2}"
    il += emit_token(0x7E, TOKENS["current_level_name"])  # ldsfld World.currentLevelName
    il += emit_token(0x72, TOKENS["slash"])  # ldstr "/"
    il += emit_token(0x28, TOKENS["find_player_block"])  # call World.FindPlayerBlock
    il += emit_token(0x7B, TOKENS["block_outer_level"])  # ldfld Block.OuterLevel
    il += emit_token(0x7B, TOKENS["level_hub_area_name"])  # ldfld Level.hubAreaName
    il += emit_token(0x28, TOKENS["string_concat_3"])  # call string.Concat(string,string,string)
    il += emit_token(0x28, TOKENS["find_player_block"])  # call World.FindPlayerBlock
    il += emit_token(0x7B, TOKENS["block_xpos"])  # ldfld Block.xpos
    il += emit_token(0x8C, TOKENS["int32"])  # box int32
    il += emit_token(0x28, TOKENS["find_player_block"])  # call World.FindPlayerBlock
    il += emit_token(0x7B, TOKENS["block_ypos"])  # ldfld Block.ypos
    il += emit_token(0x8C, TOKENS["int32"])  # box int32
    il += emit_token(0x28, TOKENS["string_format_3"])  # call string.Format(string, object, object, object)
    il += emit_token(0x28, TOKENS["debug_log"])  # call UnityEngine.Debug.Log(object)
    if include_ret:
        il += b"\x2a"  # ret
    return bytes(il)


def build_state_probe_il() -> bytes:
    il = bytearray()
    il += emit_token(0x72, TOKENS["fmt"])  # ldstr "{0} {1} {2}"
    il += emit_token(0x7E, TOKENS["state"])  # ldsfld World.State
    il += emit_token(0x8C, TOKENS["state_enum"])  # box WS
    il += emit_token(0x28, TOKENS["find_player_block"])  # call World.FindPlayerBlock
    il += emit_token(0x7B, TOKENS["block_xpos"])  # ldfld Block.xpos
    il += emit_token(0x8C, TOKENS["int32"])  # box int32
    il += emit_token(0x28, TOKENS["find_player_block"])  # call World.FindPlayerBlock
    il += emit_token(0x7B, TOKENS["block_ypos"])  # ldfld Block.ypos
    il += emit_token(0x8C, TOKENS["int32"])  # box int32
    il += emit_token(0x28, TOKENS["string_format_3"])  # call string.Format(string, object, object, object)
    il += emit_token(0x28, TOKENS["debug_log"])  # call UnityEngine.Debug.Log(object)
    il += b"\x2a"  # ret
    return bytes(il)


def build_live_blocks_lateupdate_il() -> bytes:
    il = bytearray()
    il += b"\x02"  # ldarg.0
    il += emit_token(0x28, TOKENS["world_inspect_update"])  # call World.InspectUpdate()
    il += b"\x2a"  # ret
    return bytes(il)


def build_live_blocks_helper_il() -> bytes:
    il = ILBuilder()

    # Log the standard player state line first. The reader treats following
    # numeric triples as the non-player blocks for the same frame.
    il.raw(build_position_logger_il(include_ret=False))

    # local 0 is a Block in the original InspectUpdate local signature.
    il.token(0x28, TOKENS["find_player_block"])  # call World.FindPlayerBlock
    il.emit(0x0A)  # stloc.0

    # local 4 is an int index; local 5 is a Block.
    il.emit(0x16)  # ldc.i4.0
    il.emit(0x13, 0x04)  # stloc.s 4
    il.branch(0x38, "loop_test")  # br loop_test

    il.mark("loop_body")
    il.token(0x7E, TOKENS["world_blocks"])  # ldsfld World.blocks
    il.emit(0x11, 0x04)  # ldloc.s 4
    il.token(0x6F, TOKENS["list_block_get_item"])  # callvirt get_Item
    il.emit(0x13, 0x05)  # stloc.s 5

    il.emit(0x11, 0x05)  # ldloc.s 5
    il.branch(0x39, "next_index")  # brfalse next_index

    il.emit(0x11, 0x05)  # ldloc.s 5
    il.token(0x7B, TOKENS["block_is_player"])  # ldfld Block.IsPlayer
    il.branch(0x3A, "next_index")  # brtrue next_index

    il.emit(0x11, 0x05)  # ldloc.s 5
    il.token(0x7B, TOKENS["block_sub_level"])  # ldfld Block.SubLevel
    il.branch(0x39, "next_index")  # brfalse next_index

    il.emit(0x11, 0x05)  # ldloc.s 5
    il.token(0x7B, TOKENS["block_outer_level"])  # ldfld Block.OuterLevel
    il.emit(0x06)  # ldloc.0
    il.token(0x7B, TOKENS["block_outer_level"])  # ldfld Block.OuterLevel
    il.branch(0x40, "next_index")  # bne.un next_index

    il.token(0x72, TOKENS["fmt"])  # ldstr "{0} {1} {2}"
    il.emit(0x11, 0x05)  # ldloc.s 5
    il.token(0x7B, TOKENS["block_debug_id"])  # ldfld Block.DebugID
    il.token(0x8C, TOKENS["int32"])  # box int32
    il.emit(0x11, 0x05)  # ldloc.s 5
    il.token(0x7B, TOKENS["block_xpos"])  # ldfld Block.xpos
    il.token(0x8C, TOKENS["int32"])  # box int32
    il.emit(0x11, 0x05)  # ldloc.s 5
    il.token(0x7B, TOKENS["block_ypos"])  # ldfld Block.ypos
    il.token(0x8C, TOKENS["int32"])  # box int32
    il.token(0x28, TOKENS["string_format_3"])  # call string.Format(string, object, object, object)
    il.token(0x28, TOKENS["debug_log"])  # call UnityEngine.Debug.Log(object)

    il.mark("next_index")
    il.emit(0x11, 0x04)  # ldloc.s 4
    il.emit(0x17)  # ldc.i4.1
    il.emit(0x58)  # add
    il.emit(0x13, 0x04)  # stloc.s 4

    il.mark("loop_test")
    il.emit(0x11, 0x04)  # ldloc.s 4
    il.token(0x7E, TOKENS["world_blocks"])  # ldsfld World.blocks
    il.token(0x6F, TOKENS["list_block_count"])  # callvirt get_Count
    il.branch(0x3F, "loop_body")  # blt loop_body

    il.emit(0x2A)  # ret
    return il.finish()


def method_rva(assembly: Path, type_name: str, method_name: str) -> int:
    tables = meta.load_tables(assembly)
    types = meta.type_defs(tables)
    methods = meta.methods(tables)
    type_names = [f"{item['namespace']}.{item['name']}".strip(".") for item in types]
    for index, typedef in enumerate(types):
        if type_names[index] != type_name and typedef["name"] != type_name:
            continue
        next_type = types[index + 1] if index + 1 < len(types) else None
        start = int(typedef["method_list"])
        end = int(next_type["method_list"]) if next_type else len(methods) + 1
        for method in methods[start - 1 : end - 1]:
            if method["name"] == method_name:
                return int(method["rva"])
    raise SystemExit(f"Method not found: {type_name}.{method_name}")


def patch_method_body(
    data: bytearray,
    assembly: Path,
    type_name: str,
    method_name: str,
    new_il: bytes,
    *,
    maxstack: int = 8,
) -> int:
    rva = method_rva(assembly, type_name, method_name)
    off = meta.rva_to_offset(data, rva)
    first = data[off]
    if first & 0x3 != 0x3:
        raise SystemExit(f"{type_name}.{method_name} did not use a fat method header")

    flags = meta.u16(data, off)
    header_size = (flags >> 12) * 4
    code_size = meta.u32(data, off + 4)
    body_off = off + header_size
    if len(new_il) > code_size:
        raise SystemExit(
            f"{type_name}.{method_name} logger IL is {len(new_il)} bytes "
            f"but body is only {code_size}"
        )

    # Raise maxstack for the logger and leave code_size unchanged so any
    # following sections stay at the same file offset.
    data[off + 2 : off + 4] = struct.pack("<H", maxstack)
    data[body_off : body_off + len(new_il)] = new_il
    data[body_off + len(new_il) : body_off + code_size] = b"\x00" * (code_size - len(new_il))
    return code_size


def patch(assembly: Path, *, state_probe: bool = False, live_blocks: bool = False) -> None:
    if state_probe and live_blocks:
        raise SystemExit("--state-probe and --live-blocks are mutually exclusive")

    backup = assembly.with_name(assembly.name + BACKUP_SUFFIX)
    if not backup.exists():
        shutil.copy2(assembly, backup)

    data = bytearray(assembly.read_bytes())
    patched: list[tuple[str, int, int]] = []
    if live_blocks:
        helper_il = build_live_blocks_helper_il()
        helper_size = patch_method_body(data, assembly, "World", "InspectUpdate", helper_il)
        patched.append(("World.InspectUpdate", len(helper_il), helper_size))
        late_il = build_live_blocks_lateupdate_il()
        late_size = patch_method_body(data, assembly, "World", "LateUpdate", late_il)
        patched.append(("World.LateUpdate", len(late_il), late_size))
    else:
        new_il = build_state_probe_il() if state_probe else build_position_logger_il()
        body_size = patch_method_body(data, assembly, "World", "LateUpdate", new_il)
        patched.append(("World.LateUpdate", len(new_il), body_size))

    assembly.write_bytes(data)
    print(f"patched={assembly}")
    print(f"backup={backup}")
    if live_blocks:
        mode = "live_blocks"
    elif state_probe:
        mode = "state_probe"
    else:
        mode = "position"
    print(f"mode={mode}")
    for method, il_size, body_size in patched:
        print(f"{method}.logger_il_bytes={il_size} original_body_bytes={body_size}")


def restore(assembly: Path) -> None:
    backup = assembly.with_name(assembly.name + BACKUP_SUFFIX)
    if not backup.exists():
        raise SystemExit(f"No backup found: {backup}")
    shutil.copy2(backup, assembly)
    print(f"restored={assembly}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assembly", type=Path, default=ASSEMBLY)
    parser.add_argument("--restore", action="store_true")
    parser.add_argument(
        "--state-probe",
        action="store_true",
        help="Log 'World.State x y' instead of 'level/area x y'",
    )
    parser.add_argument(
        "--live-blocks",
        action="store_true",
        help="Log player state plus live non-player block positions",
    )
    args = parser.parse_args()

    assembly = args.assembly.expanduser()
    if args.restore:
        restore(assembly)
    else:
        patch(assembly, state_probe=args.state_probe, live_blocks=args.live_blocks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
