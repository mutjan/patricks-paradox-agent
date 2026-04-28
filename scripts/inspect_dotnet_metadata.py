#!/usr/bin/env python3
"""List TypeDef/Field/Method metadata from a .NET assembly."""

from __future__ import annotations

import argparse
import struct
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ASSEMBLY = Path(
    "~/Library/Application Support/Steam/steamapps/common/"
    "Patrick's Parabox Demo/Patrick's Parabox.app/Contents/Resources/Data/Managed/Assembly-CSharp.dll"
).expanduser()


TABLE_NAMES = {
    0: "Module",
    1: "TypeRef",
    2: "TypeDef",
    3: "FieldPtr",
    4: "Field",
    5: "MethodPtr",
    6: "MethodDef",
    7: "ParamPtr",
    8: "Param",
    9: "InterfaceImpl",
    10: "MemberRef",
    11: "Constant",
    12: "CustomAttribute",
    13: "FieldMarshal",
    14: "DeclSecurity",
    15: "ClassLayout",
    16: "FieldLayout",
    17: "StandAloneSig",
    18: "EventMap",
    19: "EventPtr",
    20: "Event",
    21: "PropertyMap",
    22: "PropertyPtr",
    23: "Property",
    24: "MethodSemantics",
    25: "MethodImpl",
    26: "ModuleRef",
    27: "TypeSpec",
    28: "ImplMap",
    29: "FieldRVA",
    32: "Assembly",
    33: "AssemblyProcessor",
    34: "AssemblyOS",
    35: "AssemblyRef",
    36: "AssemblyRefProcessor",
    37: "AssemblyRefOS",
    38: "File",
    39: "ExportedType",
    40: "ManifestResource",
    41: "NestedClass",
    42: "GenericParam",
    43: "MethodSpec",
    44: "GenericParamConstraint",
}

CODED = {
    "TypeDefOrRef": (2, [2, 1, 27]),
    "HasConstant": (2, [4, 8, 23]),
    "HasCustomAttribute": (5, [6, 4, 1, 2, 8, 9, 10, 0, 14, 23, 20, 17, 26, 27, 32, 35, 38, 39, 40, 42, 43]),
    "HasFieldMarshal": (1, [4, 8]),
    "HasDeclSecurity": (2, [2, 6, 32]),
    "MemberRefParent": (3, [2, 1, 26, 6, 27]),
    "HasSemantics": (1, [20, 23]),
    "MethodDefOrRef": (1, [6, 10]),
    "MemberForwarded": (1, [4, 6]),
    "Implementation": (2, [38, 35, 39]),
    "CustomAttributeType": (3, [0, 0, 6, 10, 0]),
    "ResolutionScope": (2, [0, 26, 35, 1]),
    "TypeOrMethodDef": (1, [2, 6]),
}


@dataclass
class Streams:
    meta: bytes
    strings: bytes
    blob: bytes


@dataclass
class Tables:
    streams: Streams
    rows: dict[int, int]
    offsets: dict[int, int]
    row_sizes: dict[int, int]
    heap_sizes: int


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def u64(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def cstring(data: bytes, offset: int) -> str:
    end = data.find(b"\0", offset)
    if end < 0:
        end = len(data)
    return data[offset:end].decode("utf-8", errors="replace")


def align4(value: int) -> int:
    return (value + 3) & ~3


def rva_to_offset(data: bytes, rva: int) -> int:
    pe = u32(data, 0x3C)
    coff = pe + 4
    sections = u16(data, coff + 2)
    opt_size = u16(data, coff + 16)
    opt = coff + 20
    sec = opt + opt_size
    for i in range(sections):
        base = sec + i * 40
        virtual_size = u32(data, base + 8)
        virtual_address = u32(data, base + 12)
        raw_size = u32(data, base + 16)
        raw_pointer = u32(data, base + 20)
        size = max(virtual_size, raw_size)
        if virtual_address <= rva < virtual_address + size:
            return raw_pointer + (rva - virtual_address)
    raise ValueError(f"RVA not in sections: 0x{rva:x}")


def load_streams(path: Path) -> Streams:
    data = path.read_bytes()
    pe = u32(data, 0x3C)
    coff = pe + 4
    opt = coff + 20
    magic = u16(data, opt)
    data_dir = opt + (112 if magic == 0x20B else 96)
    cli_rva = u32(data, data_dir + 14 * 8)
    cli_off = rva_to_offset(data, cli_rva)
    meta_rva = u32(data, cli_off + 8)
    meta_off = rva_to_offset(data, meta_rva)

    if u32(data, meta_off) != 0x424A5342:
        raise SystemExit("Missing CLR metadata signature")
    version_len = u32(data, meta_off + 12)
    pos = align4(meta_off + 16 + version_len)
    streams = u16(data, pos + 2)
    pos += 4

    found: dict[str, bytes] = {}
    for _ in range(streams):
        offset = u32(data, pos)
        size = u32(data, pos + 4)
        name_start = pos + 8
        name_end = data.find(b"\0", name_start)
        name = data[name_start:name_end].decode("ascii", errors="replace")
        pos = align4(name_end + 1)
        found[name] = data[meta_off + offset : meta_off + offset + size]

    table_stream = found.get("#~") or found.get("#-")
    if table_stream is None:
        raise SystemExit("No metadata table stream")
    return Streams(table_stream, found.get("#Strings", b""), found.get("#Blob", b""))


def index_size(rows: dict[int, int], table: int) -> int:
    return 4 if rows.get(table, 0) >= 65536 else 2


def coded_size(rows: dict[int, int], name: str) -> int:
    tag_bits, tables = CODED[name]
    max_rows = max(rows.get(table, 0) for table in tables)
    return 4 if max_rows >= (1 << (16 - tag_bits)) else 2


def table_row_size(table: int, rows: dict[int, int], heap_sizes: int) -> int:
    s = 4 if heap_sizes & 0x01 else 2
    g = 4 if heap_sizes & 0x02 else 2
    b = 4 if heap_sizes & 0x04 else 2
    idx = lambda t: index_size(rows, t)
    coded = lambda n: coded_size(rows, n)
    sizes = {
        0: 2 + s + g + g + g,
        1: coded("ResolutionScope") + s + s,
        2: 4 + s + s + coded("TypeDefOrRef") + idx(4) + idx(6),
        3: idx(4),
        4: 2 + s + b,
        5: idx(6),
        6: 4 + 2 + 2 + s + b + idx(8),
        7: idx(8),
        8: 2 + 2 + s,
        9: idx(2) + coded("TypeDefOrRef"),
        10: coded("MemberRefParent") + s + b,
        11: 2 + coded("HasConstant") + b,
        12: coded("HasCustomAttribute") + coded("CustomAttributeType") + b,
        13: coded("HasFieldMarshal") + b,
        14: 2 + coded("HasDeclSecurity") + b,
        15: 2 + 4 + idx(2),
        16: 4 + idx(4),
        17: b,
        18: idx(2) + idx(20),
        19: idx(20),
        20: 2 + s + coded("TypeDefOrRef"),
        21: idx(2) + idx(23),
        22: idx(23),
        23: 2 + s + b,
        24: 2 + idx(6) + coded("HasSemantics"),
        25: idx(2) + coded("MethodDefOrRef") + coded("MethodDefOrRef"),
        26: s,
        27: b,
        28: 2 + coded("MemberForwarded") + s + idx(26),
        29: 4 + idx(4),
        32: 4 + 2 + 2 + 2 + 2 + 4 + b + s + s,
        33: 4,
        34: 4 + 4 + 4,
        35: 2 + 2 + 2 + 2 + 4 + b + s + s + b,
        36: 4 + idx(35),
        37: 4 + 4 + 4 + idx(35),
        38: 4 + s + b,
        39: 4 + 4 + s + s + coded("Implementation"),
        40: 4 + 4 + s + coded("Implementation"),
        41: idx(2) + idx(2),
        42: 2 + 2 + coded("TypeOrMethodDef") + s,
        43: coded("MethodDefOrRef") + b,
        44: idx(42) + coded("TypeDefOrRef"),
    }
    return sizes[table]


def load_tables(path: Path) -> Tables:
    streams = load_streams(path)
    meta = streams.meta
    heap_sizes = meta[6]
    valid = u64(meta, 8)
    pos = 24
    rows: dict[int, int] = {}
    for table in range(64):
        if valid & (1 << table):
            rows[table] = u32(meta, pos)
            pos += 4
    row_sizes = {table: table_row_size(table, rows, heap_sizes) for table in rows}
    offsets: dict[int, int] = {}
    for table in range(64):
        if table in rows:
            offsets[table] = pos
            pos += rows[table] * row_sizes[table]
    return Tables(streams, rows, offsets, row_sizes, heap_sizes)


def read_index(data: bytes, offset: int, size: int) -> int:
    return u32(data, offset) if size == 4 else u16(data, offset)


def str_at(strings: bytes, index: int) -> str:
    return "" if index == 0 else cstring(strings, index)


def type_defs(tables: Tables) -> list[dict[str, object]]:
    meta = tables.streams.meta
    rows = tables.rows
    s = 4 if tables.heap_sizes & 0x01 else 2
    field_index_size = index_size(rows, 4)
    method_index_size = index_size(rows, 6)
    extends_size = coded_size(rows, "TypeDefOrRef")
    out = []
    pos = tables.offsets[2]
    for rid in range(1, rows.get(2, 0) + 1):
        name_idx = read_index(meta, pos + 4, s)
        ns_idx = read_index(meta, pos + 4 + s, s)
        p = pos + 4 + s + s + extends_size
        field_list = read_index(meta, p, field_index_size)
        method_list = read_index(meta, p + field_index_size, method_index_size)
        name = str_at(tables.streams.strings, name_idx)
        namespace = str_at(tables.streams.strings, ns_idx)
        out.append({"rid": rid, "name": name, "namespace": namespace, "field_list": field_list, "method_list": method_list})
        pos += tables.row_sizes[2]
    return out


def fields(tables: Tables) -> list[str]:
    meta = tables.streams.meta
    s = 4 if tables.heap_sizes & 0x01 else 2
    out = []
    pos = tables.offsets[4]
    for _ in range(tables.rows.get(4, 0)):
        name_idx = read_index(meta, pos + 2, s)
        out.append(str_at(tables.streams.strings, name_idx))
        pos += tables.row_sizes[4]
    return out


def methods(tables: Tables) -> list[dict[str, object]]:
    meta = tables.streams.meta
    s = 4 if tables.heap_sizes & 0x01 else 2
    b = 4 if tables.heap_sizes & 0x04 else 2
    param_index_size = index_size(tables.rows, 8)
    out = []
    pos = tables.offsets[6]
    for rid in range(1, tables.rows.get(6, 0) + 1):
        rva = u32(meta, pos)
        name_idx = read_index(meta, pos + 8, s)
        out.append({"rid": rid, "rva": rva, "name": str_at(tables.streams.strings, name_idx)})
        pos += 4 + 2 + 2 + s + b + param_index_size
    return out


def member_refs(tables: Tables) -> list[str]:
    meta = tables.streams.meta
    s = 4 if tables.heap_sizes & 0x01 else 2
    b = 4 if tables.heap_sizes & 0x04 else 2
    parent_size = coded_size(tables.rows, "MemberRefParent")
    out = []
    pos = tables.offsets.get(10, 0)
    for _ in range(tables.rows.get(10, 0)):
        name_idx = read_index(meta, pos + parent_size, s)
        out.append(str_at(tables.streams.strings, name_idx))
        pos += parent_size + s + b
    return out


OPCODES: dict[int, tuple[str, str]] = {
    0x00: ("nop", "none"), 0x01: ("break", "none"), 0x02: ("ldarg.0", "none"), 0x03: ("ldarg.1", "none"),
    0x04: ("ldarg.2", "none"), 0x05: ("ldarg.3", "none"), 0x06: ("ldloc.0", "none"), 0x07: ("ldloc.1", "none"),
    0x08: ("ldloc.2", "none"), 0x09: ("ldloc.3", "none"), 0x0A: ("stloc.0", "none"), 0x0B: ("stloc.1", "none"),
    0x0C: ("stloc.2", "none"), 0x0D: ("stloc.3", "none"), 0x0E: ("ldarg.s", "u1"), 0x0F: ("ldarga.s", "u1"),
    0x10: ("starg.s", "u1"), 0x11: ("ldloc.s", "u1"), 0x12: ("ldloca.s", "u1"), 0x13: ("stloc.s", "u1"),
    0x14: ("ldnull", "none"), 0x15: ("ldc.i4.m1", "none"), 0x16: ("ldc.i4.0", "none"), 0x17: ("ldc.i4.1", "none"),
    0x18: ("ldc.i4.2", "none"), 0x19: ("ldc.i4.3", "none"), 0x1A: ("ldc.i4.4", "none"), 0x1B: ("ldc.i4.5", "none"),
    0x1C: ("ldc.i4.6", "none"), 0x1D: ("ldc.i4.7", "none"), 0x1E: ("ldc.i4.8", "none"), 0x1F: ("ldc.i4.s", "i1"),
    0x20: ("ldc.i4", "i4"), 0x21: ("ldc.i8", "i8"), 0x22: ("ldc.r4", "r4"), 0x23: ("ldc.r8", "r8"),
    0x25: ("dup", "none"), 0x26: ("pop", "none"), 0x28: ("call", "token"), 0x2A: ("ret", "none"),
    0x2B: ("br.s", "br1"), 0x2C: ("brfalse.s", "br1"), 0x2D: ("brtrue.s", "br1"), 0x2E: ("beq.s", "br1"),
    0x2F: ("bge.s", "br1"), 0x30: ("bgt.s", "br1"), 0x31: ("ble.s", "br1"), 0x32: ("blt.s", "br1"),
    0x33: ("bne.un.s", "br1"), 0x34: ("bge.un.s", "br1"), 0x35: ("bgt.un.s", "br1"), 0x36: ("ble.un.s", "br1"),
    0x37: ("blt.un.s", "br1"), 0x38: ("br", "br4"), 0x39: ("brfalse", "br4"), 0x3A: ("brtrue", "br4"),
    0x3B: ("beq", "br4"), 0x3C: ("bge", "br4"), 0x3D: ("bgt", "br4"), 0x3E: ("ble", "br4"),
    0x3F: ("blt", "br4"), 0x40: ("bne.un", "br4"), 0x41: ("bge.un", "br4"), 0x42: ("bgt.un", "br4"),
    0x43: ("ble.un", "br4"), 0x44: ("blt.un", "br4"), 0x45: ("switch", "switch"), 0x58: ("add", "none"),
    0x59: ("sub", "none"), 0x5A: ("mul", "none"), 0x5B: ("div", "none"), 0x5D: ("rem", "none"),
    0x5F: ("and", "none"), 0x60: ("or", "none"), 0x61: ("xor", "none"), 0x62: ("shl", "none"),
    0x63: ("shr", "none"), 0x65: ("neg", "none"), 0x66: ("not", "none"), 0x67: ("conv.i1", "none"),
    0x68: ("conv.i2", "none"), 0x69: ("conv.i4", "none"), 0x6A: ("conv.i8", "none"), 0x6B: ("conv.r4", "none"),
    0x6C: ("conv.r8", "none"), 0x6D: ("conv.u4", "none"), 0x6E: ("conv.u8", "none"), 0x6F: ("callvirt", "token"),
    0x70: ("cpobj", "token"), 0x71: ("ldobj", "token"), 0x72: ("ldstr", "token"), 0x73: ("newobj", "token"),
    0x74: ("castclass", "token"), 0x75: ("isinst", "token"), 0x76: ("conv.r.un", "none"), 0x79: ("unbox", "token"),
    0x7A: ("throw", "none"), 0x7B: ("ldfld", "token"), 0x7C: ("ldflda", "token"), 0x7D: ("stfld", "token"),
    0x7E: ("ldsfld", "token"), 0x7F: ("ldsflda", "token"), 0x80: ("stsfld", "token"), 0x81: ("stobj", "token"),
    0x8C: ("box", "token"), 0x8D: ("newarr", "token"), 0x8E: ("ldlen", "none"), 0x8F: ("ldelema", "token"),
    0x90: ("ldelem.i1", "none"), 0x91: ("ldelem.u1", "none"), 0x92: ("ldelem.i2", "none"), 0x93: ("ldelem.u2", "none"),
    0x94: ("ldelem.i4", "none"), 0x95: ("ldelem.u4", "none"), 0x96: ("ldelem.i8", "none"), 0x97: ("ldelem.i", "none"),
    0x98: ("ldelem.r4", "none"), 0x99: ("ldelem.r8", "none"), 0x9A: ("ldelem.ref", "none"), 0x9B: ("stelem.i", "none"),
    0x9C: ("stelem.i1", "none"), 0x9D: ("stelem.i2", "none"), 0x9E: ("stelem.i4", "none"), 0x9F: ("stelem.i8", "none"),
    0xA0: ("stelem.r4", "none"), 0xA1: ("stelem.r8", "none"), 0xA2: ("stelem.ref", "none"), 0xA3: ("ldelem", "token"),
    0xA4: ("stelem", "token"), 0xA5: ("unbox.any", "token"), 0xB6: ("conv.ovf.i4", "none"), 0xC2: ("refanyval", "token"),
    0xC3: ("ckfinite", "none"), 0xD0: ("ldtoken", "token"), 0xD1: ("conv.u2", "none"), 0xD2: ("conv.u1", "none"),
    0xD3: ("conv.i", "none"), 0xD4: ("conv.ovf.i", "none"), 0xD5: ("conv.ovf.u", "none"), 0xD6: ("add.ovf", "none"),
    0xD7: ("add.ovf.un", "none"), 0xD8: ("mul.ovf", "none"), 0xD9: ("mul.ovf.un", "none"), 0xDA: ("sub.ovf", "none"),
    0xDB: ("sub.ovf.un", "none"), 0xDC: ("endfinally", "none"), 0xDD: ("leave", "br4"), 0xDE: ("leave.s", "br1"),
    0xDF: ("stind.i", "none"), 0xE0: ("conv.u", "none"),
    0xFE01: ("ceq", "none"), 0xFE02: ("cgt", "none"), 0xFE03: ("cgt.un", "none"), 0xFE04: ("clt", "none"),
    0xFE05: ("clt.un", "none"), 0xFE06: ("ldftn", "token"), 0xFE07: ("ldvirtftn", "token"), 0xFE09: ("ldarg", "u2"),
    0xFE0A: ("ldarga", "u2"), 0xFE0B: ("starg", "u2"), 0xFE0C: ("ldloc", "u2"), 0xFE0D: ("ldloca", "u2"),
    0xFE0E: ("stloc", "u2"), 0xFE0F: ("localloc", "none"), 0xFE11: ("endfilter", "none"), 0xFE12: ("unaligned.", "u1"),
    0xFE13: ("volatile.", "none"), 0xFE14: ("tail.", "none"), 0xFE15: ("initobj", "token"), 0xFE16: ("constrained.", "token"),
    0xFE17: ("cpblk", "none"), 0xFE18: ("initblk", "none"), 0xFE1A: ("rethrow", "none"), 0xFE1C: ("sizeof", "token"),
    0xFE1D: ("refanytype", "none"), 0xFE1E: ("readonly.", "none"),
}


def token_name(token: int, type_names: list[str], field_names: list[str], method_names: list[str], member_names: list[str]) -> str:
    table = token >> 24
    rid = token & 0x00FFFFFF
    if rid == 0:
        return ""
    if table == 0x02 and rid <= len(type_names):
        return type_names[rid - 1]
    if table == 0x04 and rid <= len(field_names):
        return field_names[rid - 1]
    if table == 0x06 and rid <= len(method_names):
        return method_names[rid - 1]
    if table == 0x0A and rid <= len(member_names):
        return member_names[rid - 1]
    return ""


def il_bytes(assembly_data: bytes, rva: int) -> bytes:
    off = rva_to_offset(assembly_data, rva)
    first = assembly_data[off]
    if first & 0x3 == 0x2:
        size = first >> 2
        return assembly_data[off + 1 : off + 1 + size]
    flags = u16(assembly_data, off)
    header_size = (flags >> 12) * 4
    code_size = u32(assembly_data, off + 4)
    return assembly_data[off + header_size : off + header_size + code_size]


def disassemble(code: bytes, names: tuple[list[str], list[str], list[str], list[str]]) -> list[str]:
    type_names, field_names, method_names, member_names = names
    out: list[str] = []
    pos = 0
    while pos < len(code):
        start = pos
        op = code[pos]
        pos += 1
        if op == 0xFE:
            op = 0xFE00 | code[pos]
            pos += 1
        name, operand = OPCODES.get(op, (f"op_{op:x}", "none"))
        value = ""
        if operand == "u1":
            value = str(code[pos]); pos += 1
        elif operand == "i1":
            value = str(struct.unpack_from("b", code, pos)[0]); pos += 1
        elif operand == "u2":
            value = str(u16(code, pos)); pos += 2
        elif operand == "i4":
            value = str(struct.unpack_from("<i", code, pos)[0]); pos += 4
        elif operand == "i8":
            value = str(struct.unpack_from("<q", code, pos)[0]); pos += 8
        elif operand == "r4":
            value = str(struct.unpack_from("<f", code, pos)[0]); pos += 4
        elif operand == "r8":
            value = str(struct.unpack_from("<d", code, pos)[0]); pos += 8
        elif operand == "br1":
            delta = struct.unpack_from("b", code, pos)[0]; pos += 1
            value = f"IL_{pos + delta:04x}"
        elif operand == "br4":
            delta = struct.unpack_from("<i", code, pos)[0]; pos += 4
            value = f"IL_{pos + delta:04x}"
        elif operand == "token":
            token = u32(code, pos); pos += 4
            resolved = token_name(token, type_names, field_names, method_names, member_names)
            value = f"0x{token:08x}" + (f" {resolved}" if resolved else "")
        elif operand == "switch":
            count = u32(code, pos); pos += 4
            deltas = [struct.unpack_from("<i", code, pos + i * 4)[0] for i in range(count)]
            pos += count * 4
            value = ", ".join(f"IL_{pos + d:04x}" for d in deltas)
        out.append(f"IL_{start:04x}: {name}" + (f" {value}" if value else ""))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assembly", type=Path, default=DEFAULT_ASSEMBLY)
    parser.add_argument("--filter", default="", help="Case-insensitive substring filter")
    parser.add_argument("--members", action="store_true", help="Print fields and methods for matching types")
    parser.add_argument("--il", help="Dump IL for Type.Method, e.g. Movement.AttemptToEnter")
    args = parser.parse_args()

    assembly_path = args.assembly.expanduser()
    tables = load_tables(assembly_path)
    types = type_defs(tables)
    all_fields = fields(tables)
    all_methods = methods(tables)
    all_member_refs = member_refs(tables)
    type_names = [f"{item['namespace']}.{item['name']}".strip(".") for item in types]
    field_names = all_fields
    method_names = [str(item["name"]) for item in all_methods]

    if args.il:
        type_part, method_part = args.il.rsplit(".", 1)
        if method_part == "ctor":
            method_part = ".ctor"
            type_part = type_part.rstrip(".")
        if method_part == "cctor":
            method_part = ".cctor"
            type_part = type_part.rstrip(".")
        for index, typedef in enumerate(types):
            fullname = type_names[index]
            if fullname != type_part and str(typedef["name"]) != type_part:
                continue
            next_type = types[index + 1] if index + 1 < len(types) else None
            method_start = int(typedef["method_list"])
            method_end = int(next_type["method_list"]) if next_type else len(all_methods) + 1
            for method in all_methods[method_start - 1 : method_end - 1]:
                if method["name"] == method_part:
                    code = il_bytes(assembly_path.read_bytes(), int(method["rva"]))
                    print(f"{fullname}.{method_part} rva=0x{int(method['rva']):x} code_size={len(code)}")
                    print("\n".join(disassemble(code, (type_names, field_names, method_names, all_member_refs))))
                    return 0
        raise SystemExit(f"Method not found: {args.il}")

    needle = args.filter.lower()

    for index, typedef in enumerate(types):
        fullname = f"{typedef['namespace']}.{typedef['name']}".strip(".")
        next_type = types[index + 1] if index + 1 < len(types) else None
        field_start = int(typedef["field_list"])
        field_end = int(next_type["field_list"]) if next_type else len(all_fields) + 1
        method_start = int(typedef["method_list"])
        method_end = int(next_type["method_list"]) if next_type else len(all_methods) + 1
        type_fields = all_fields[field_start - 1 : field_end - 1]
        type_methods = all_methods[method_start - 1 : method_end - 1]
        haystack = " ".join([fullname, *type_fields, *(str(m["name"]) for m in type_methods)]).lower()
        if needle and needle not in haystack:
            continue
        print(f"{int(typedef['rid']):04d} {fullname} fields={len(type_fields)} methods={len(type_methods)}")
        if args.members:
            if type_fields:
                print("  fields: " + ", ".join(type_fields))
            if type_methods:
                print("  methods: " + ", ".join(f"{m['name']}@0x{int(m['rva']):x}" for m in type_methods))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
