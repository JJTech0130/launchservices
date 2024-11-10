from io import BytesIO
from typing import Self
from dataclasses import dataclass
import click

FLAG_CATALOG = 0x40000000
ALL_FLAGS = FLAG_CATALOG

@dataclass
class CSUnit:
    id: int
    flags: int
    data: bytes

    @classmethod
    def from_stream(cls, d: BytesIO) -> Self:
        id_and_flags = int.from_bytes(d.read(4), "little")
        id = (id_and_flags &~ ALL_FLAGS) << 2
        flags = id_and_flags & ALL_FLAGS
        size = int.from_bytes(d.read(4), "little")
        data = d.read(size)
        return cls(id, flags, data)
    
def hashmap_from_stream(d: BytesIO, start: int) -> dict:
    map = {}
    tell = d.tell()
    d.seek(start)
    bucket_count = int.from_bytes(d.read(4), "little")
    for _ in range(bucket_count):
        item_count = int.from_bytes(d.read(4), "little")
        items_offset = int.from_bytes(d.read(4), "little")
        t = d.tell()
        d.seek(items_offset)
        for _ in range(item_count):
            key = int.from_bytes(d.read(4), "little")
            v = int.from_bytes(d.read(4), "little")
            tv = d.tell()
            d.seek(v)
            value = CSUnit.from_stream(d)
            d.seek(tv)
            map[key] = value
        d.seek(t)
    d.seek(tell)
    return map
        
@dataclass
class CSTable(CSUnit):
    name: str
    next_unit_id: int
    extra: bytes
    hashmap: dict[int, CSUnit]
    
    @classmethod
    def from_unit(cls, unit: CSUnit, d: BytesIO) -> Self:
        da = BytesIO(unit.data)
        name = da.read(0x30).strip(b"\x00").decode("utf-8")
        da.read(0x10)
        next_unit_id = int.from_bytes(da.read(4), "little") * 4
        hashmap_header_start = int.from_bytes(da.read(4), "little")
        extra = da.read()
        hashmap = hashmap_from_stream(d, hashmap_header_start)
        return cls(unit.id, unit.flags, unit.data, name, next_unit_id, extra, hashmap)

@dataclass
class CSStore:
    magic = b"bdsl"
    version = 2
    crc: int
    size1: int
    size2: int
    catalog: CSTable
    tables: dict[int, CSTable]

    @classmethod
    def from_bytes(cls, data: bytes):
        d = BytesIO(data)

        # Header
        assert d.read(4) == cls.magic
        assert d.read(1) == cls.version.to_bytes(1, "little")
        d.read(1)
        crc = int.from_bytes(d.read(2), "little")
        d.read(4)
        size1 = int.from_bytes(d.read(4), "little")
        size2 = int.from_bytes(d.read(4), "little")

        catalog = CSUnit.from_stream(d)
        assert catalog.flags & FLAG_CATALOG
        catalog = CSTable.from_unit(catalog, d)

        tables = {}

        for key, value in catalog.hashmap.items():
            tables[key] = CSTable.from_unit(value, d)

        return cls(crc, size1, size2, catalog, tables)
    
    def get_table(self, name: str) -> CSTable:
        for table in self.tables.values():
            if table.name == name:
                return table
        raise KeyError(f"Table {name} not found")
    
    def get_array(self, key: int) -> list:
        b = self.get_table("<array>").hashmap[key].data
        #print(key)
        #print(b.hex())
        d = BytesIO(b)
        count = int.from_bytes(d.read(4), "little")
        full = count & 0x20000000
        count &= ~0x20000000
        out = []
        for _ in range(count):
            if full:
                out.append(int.from_bytes(d.read(4), "little"))
            else:
                out.append(int.from_bytes(d.read(2), "little"))
        return out
    
    def get_string(self, key: int) -> str:
        return self.get_table("<string>").hashmap[key].data.decode("utf-8")

def unpack_string(data: int) -> str:
    packed_alphabet = '\x00 abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    return ''.join(packed_alphabet[(data >> (2 + 6 * i)) & 0x3f] for i in range(5)).rstrip('\x00')[::-1]

LSBinding = dict[str, list[str]]

@dataclass
class LSClaim(CSUnit):
    claim_flags: "LSClaim.Flags"
    rank: int
    roles: list[str]
    unknown: int
    localized_names: list[str]
    req_caps: list[str]
    icon_files: list[str]
    icon_name: str
    delegate: str
    bindings: LSBinding

    class Flags:
        apple_default = 0x1
        apple_default_no_override = 0x2
        apple_internal = 0x4
        relative_icon_path = 0x1000
        package = 0x8
        legacy_wildcard = 0x10
        doc_type = 0x20
        url_type = 0x40
        private_scheme = 0x80
        always_available = 0x100
        resolves_icloud_conflicts = 0x200
        uti_wildcard = 0x400
        supports_collaboration = 0x800

        def __init__(self, flags: int):
            self.flags = flags
        
        def __str__(self):
            out = []
            if self.flags & self.apple_default:
                out.append("apple-default")
            if self.flags & self.apple_internal:
                out.append("apple-internal")
            if self.flags & self.relative_icon_path:
                out.append("relative-icon-path")
            if self.flags & self.package:
                out.append("package")
            if self.flags & self.legacy_wildcard:
                out.append("wildcard")
            if self.flags & self.doc_type:
                out.append("doc-type")
            if self.flags & self.url_type:
                out.append("url-type")
            if self.flags & self.private_scheme:
                out.append("private-scheme")
            if self.flags & self.always_available:
                out.append("always-available")
            if self.flags & self.resolves_icloud_conflicts:
                out.append("resolves-icloud-conflicts")
            return ", ".join(out)
        
        def __repr__(self):
            return "[" + str(self) + "]"
        
    class Roles:
        none = 0x1
        viewer = 0x2
        editor = 0x4
        shell = 0x8
        importer = 0x10
        qlgenerator = 0x20

        def __init__(self, roles: int):
            self.roles = roles
        
        def __str__(self):
            out = []
            if self.roles & self.none:
                out.append("none")
            if self.roles & self.viewer:
                out.append("viewer")
            if self.roles & self.editor:
                out.append("editor")
            if self.roles & self.shell:
                out.append("shell")
            if self.roles & self.importer:
                out.append("importer")
            if self.roles & self.qlgenerator:
                out.append("qlgenerator")
            return ", ".join(out)
        
        def __repr__(self):
            return "[" + str(self) + "]"

#     claim id:                   Numbers document (0x608)
# localizedNames:             "LSDefaultLocalizedValue" = "Numbers document"
# rank:                       Default
# bundle:                     com.apple.system-library (0x140)
# flags:                      apple-internal  package  doc-type (000000000000002c)
# roles:                      Importer (0000000000000010)
# delegate:                   Spotlight/iWork.mdimporter/
# bindings:                   com.apple.iwork.numbers.numbers-tef
        

    @classmethod
    def from_unit(cls, unit: CSUnit, database: "LSDatabase") -> Self:
        d = BytesIO(unit.data)
        d.read(8)

        flags = cls.Flags(int.from_bytes(d.read(4), "little"))

        rank = int.from_bytes(d.read(2), "little")
        roles = cls.Roles(int.from_bytes(d.read(2), "little"))

        unknown = int.from_bytes(d.read(4), "little")
        
        #localized_names = database.get_string_array(int.from_bytes(d.read(4), "little"))
        localized_names = ["TODO"]
        d.read(4)
        
        req_caps = database.get_string_array(int.from_bytes(d.read(4), "little"))
        icon_files = database.get_string_array(int.from_bytes(d.read(4), "little"))
        icon_name = database.store.get_string(int.from_bytes(d.read(4), "little"))
        delegate = database.store.get_string(int.from_bytes(d.read(4), "little"))
        bindings = database.binding_list[int.from_bytes(d.read(4), "little")]

        return cls(unit.id, unit.flags, unit.data, flags, rank, roles, unknown, localized_names, req_caps, icon_files, icon_name, delegate, bindings)

@dataclass
class LSDatabase:
    store: CSStore
    binding_list: dict[int, LSBinding] = None

    def __post_init__(self):
        self.binding_list = self._get_binding_list()

    @classmethod
    def from_bytes(cls, data: bytes):
        store = CSStore.from_bytes(data)
        return cls(store)
    
    def _get_binding_list(self) -> dict[int, LSBinding]:
        binding_list = self.store.get_table("BindingList")
        out = {}
        for key, value in binding_list.hashmap.items():
            d = BytesIO(value.data)
            list_count = int.from_bytes(d.read(4), "little")
            out_inner = {}
            for _ in range(list_count):
                name = self.store.get_string(int.from_bytes(d.read(4), "little"))
                value_count = int.from_bytes(d.read(4), "little")
                values = []
                for _ in range(value_count):
                    value = int.from_bytes(d.read(4), "little")
                    if value & 1:
                        value = unpack_string(value)
                    else:
                        value = self.store.get_string(value)
                    values.append(value)
                out_inner[name] = values
            out[key] = out_inner
        return out
    
    def get_claims(self):
        claims = self.store.get_table("Claim")
        out = {}
#         0x08 flags
# 0x0e roles
# 0x10 ????
# 0x14 localizedNames
# 0x18 reqCaps
# 0x1c iconFiles
# 0x20 iconName
# 0x24 delegate
# 0x28 bindings
        # Sort the hashmap
        claims.hashmap = dict(sorted(claims.hashmap.items()))
        cl = len(list(claims.hashmap.values())[1].data)
        for key, value in claims.hashmap.items():
            if value.data == b"":
                out[key] = None
                continue
            #out[key] = LSClaim.from_unit(value, self)
            #print(out[key])
            if len(value.data) != cl:
                print("odd claim")

        print("claim length", cl)
        return out

    def get_string_array(self, key: int) -> list[str]:
        return [self.store.get_string(x) for x in self.store.get_array(key)]

            

@click.group()
@click.argument("store_path")
@click.pass_context
def cli(ctx, store_path: str):
    raw_store = open(store_path, "rb").read()
    store = CSStore.from_bytes(raw_store)
    ctx.obj = store

@cli.command()
@click.argument("dump_path")
@click.pass_context
def dump(ctx, dump_path: str):
    store: CSStore = ctx.obj
    with open(dump_path, "w") as f:
        import pprint
        pprint.pprint(store, f, width=800)

def hexdump(b: bytes):
    d = BytesIO(b)
    def _format_byte(b: int) -> str:
        return f"{b:02x}" if b != 0 else click.style("00", fg="black")
    while True:
        chunk = d.read(16)
        if not chunk:
            break
        #click.echo(binascii.hexlify(chunk).decode("utf-8") + " ", nl=False)
        # start addr
        click.echo(f"{d.tell() - 16:08x} ", nl=False)
        click.echo(" ".join(_format_byte(x) for x in chunk) + " ", nl=False)
        click.echo("".join(chr(x) if 32 <= x < 127 else click.style(".", "black") for x in chunk), nl=True)

@cli.command()
@click.pass_context
def header(ctx):
    store: CSStore = ctx.obj
    database = LSDatabase(store)

    header = database.store.get_table("DB Header").extra

    hexdump(header)

    click.echo()
    click.echo(f"DB Header len:\t{len(header)}")

    h = BytesIO(header)
    click.echo(f"DB Schema: \t{int.from_bytes(h.read(4), "little")}")
    l = int.from_bytes(h.read(4), "little")

    while h.tell() < l:
        key = int.from_bytes(h.read(4), "little")
        assert int.from_bytes(h.read(4), "little") == 0x0
        if key & 0x0F000000 != 0:
            click.echo(f"{(key &~ 0x0F000000):02x}")
            break
        click.echo(f"{key:02x} ", nl=False)

    click.echo(f"Build:\t\t{h.read(0x10).decode("utf-8")}")
    click.echo(f"Model:\t\t{h.read(0x20).decode("utf-8")}")

if __name__ == "__main__":
    cli()