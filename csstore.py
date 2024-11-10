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
    
    def get_string(self, key: int) -> str:
        return self.get_table("<string>").hashmap[key].data.decode("utf-8")

def unpack_string(data: int) -> str:
    packed_alphabet = '\x00 abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    return ''.join(packed_alphabet[(data >> (2 + 6 * i)) & 0x3f] for i in range(5)).rstrip('\x00')[::-1]

@dataclass
class LSDatabase:
    store: CSStore

    @classmethod
    def from_bytes(cls, data: bytes):
        store = CSStore.from_bytes(data)
        return cls(store)
    
    def get_binding_list(self) -> dict[int, dict[str, list[str]]]:
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

@cli.command()
@click.pass_context
def test(ctx):
    store: CSStore = ctx.obj
    database = LSDatabase(store)
    print(database.get_binding_list())

if __name__ == "__main__":
    cli()