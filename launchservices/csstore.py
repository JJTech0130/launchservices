from io import BytesIO
from typing import Self
from dataclasses import dataclass

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