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

            map[key] = v
        d.seek(t)
    d.seek(tell)
    return map
        
@dataclass
class CSTable(CSUnit):
    name: str
    _next_unit_id: int
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
        for key, value in hashmap.items():
            d.seek(value)
            hashmap[key] = CSUnit.from_stream(d)
        return cls(unit.id, unit.flags, unit.data, name, next_unit_id, extra, hashmap)
    
    def store_unit(self, unit: CSUnit) -> int:
        unit.id = self._next_unit_id
        self.hashmap[unit.id] = unit
        self._next_unit_id += 4
        return unit.id

@dataclass
class CSStringContainer:
    _strings: CSTable
    _refcnt: dict[int, int]

    @classmethod
    def from_store(cls, s: CSTable, d: BytesIO) -> Self:
        ref = int.from_bytes(s.extra, "little")
        refcnt = hashmap_from_stream(d, ref)

        for key, value in refcnt.items():
            assert (value & 0xFF00 == 0x100) or (value == 0)
            refcnt[key] = value & 0xFF # "Hints" are also stored here, usually 0x100
        return cls(s, refcnt)
    
    def get_string(self, key: int) -> str:
        return self._strings.hashmap[key].data.decode("utf-8")
    
    def retain_string(self, key: int):
        self._refcnt[key] += 1
    
    def release_string(self, key: int):
        self._refcnt[key] -= 1
        if self._refcnt[key] == 0:
            del self._refcnt[key]

    def store_string(self, s: str) -> int:
        key = self._strings.store_unit(CSUnit(0, 0, s.encode("utf-8")))
        self._refcnt[key] = 1
        return key

@dataclass
class CSStore:
    magic = b"bdsl"
    version = 2
    crc: int
    size1: int
    size2: int
    catalog: CSTable
    strings: CSStringContainer
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
        strings = None

        for key, value in catalog.hashmap.items():
            table = CSTable.from_unit(value, d)
            if table.name == "<string>":
                strings = CSStringContainer.from_store(table, d)
                continue
            else:
                tables[key] = table

        assert strings

        return cls(crc, size1, size2, catalog, strings, tables)
    
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