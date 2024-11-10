from io import BytesIO
from typing import Self
from dataclasses import dataclass

FLAG_CATALOG = 0x40000000
ALL_FLAGS = FLAG_CATALOG

@dataclass
class CSUnit:
    id: int
    flags: int
    size: int
    data: bytes

    @classmethod
    def from_stream(cls, d: BytesIO) -> Self:
        id_and_flags = int.from_bytes(d.read(4), "little")
        id = (id_and_flags &~ ALL_FLAGS) << 2
        flags = id_and_flags & ALL_FLAGS
        size = int.from_bytes(d.read(4), "little")
        data = d.read(size)
        return cls(id, flags, size, data)

@dataclass
class CSHashMap:
    map: dict

    @classmethod
    def from_stream(cls, d: BytesIO, start: int) -> Self:
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
        return cls(map)
        
@dataclass
class CSTable(CSUnit):
    name: str
    next_unit: int
    extra: bytes
    hashmap: CSHashMap
    
    @classmethod
    def from_unit(cls, unit: CSUnit, d: BytesIO) -> Self:
        da = BytesIO(unit.data)
        name = da.read(0x30).strip(b"\x00").decode("utf-8")
        da.read(0x10)
        next_unit = int.from_bytes(da.read(4), "little")
        hashmap_header_start = int.from_bytes(da.read(4), "little")
        extra = da.read()
        hashmap = CSHashMap.from_stream(d, hashmap_header_start)
        return cls(unit.id, unit.flags, unit.size, unit.data, name, next_unit, extra, hashmap)

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
        #cls = cls()
        
        # Header
        assert d.read(4) == cls.magic
        assert d.read(1) == cls.version.to_bytes(1, "little")
        d.read(1)
        crc = int.from_bytes(d.read(2), "little")
        d.read(4)
        size1 = int.from_bytes(d.read(4), "little")
        size2 = int.from_bytes(d.read(4), "little")

        catalog = CSTable.from_unit(CSUnit.from_stream(d), d)

        tables = {}

        for key, value in catalog.hashmap.map.items():
            tables[key] = CSTable.from_unit(value, d)

        return cls(crc, size1, size2, catalog, tables)

if __name__ == "__main__":
    raw_store = open("./samples/com.apple.LaunchServices-5019-v2.csstore", "rb").read()
    store = CSStore.from_bytes(raw_store)

    import pprint
    with open("csstore.txt", "w") as f:
        pprint.pprint(store, f, width=800)