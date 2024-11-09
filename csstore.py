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

def unpack_6bit_string(packed_bytes):
    """Unpack a 6-bit packed string."""

    # Define a mapping of 6-bit values to characters
    bit_to_char = {i: chr(i+64) for i in range(64)}

    # Unpack the bytes into bits
    bits = []
    for byte in packed_bytes:
        for i in range(8):
            if (byte >> (7 - i)) & 1:
                bits.append(1)
            else:
                bits.append(0)

    # Decode the bits into characters
    string = ""
    current_char = 0
    bit_count = 0
    for bit in bits:
        current_char |= bit << (5 - bit_count)
        bit_count += 1
        if bit_count >= 6:
            string += bit_to_char[current_char]
            current_char = 0
            bit_count -= 6

    return string

def unpack_7bit(packed_bytes):
    """Unpacks a 7-bit packed string."""

    result = []
    current_byte = 0
    bit_count = 0

    for byte in packed_bytes:
        current_byte |= (byte << bit_count)
        bit_count += 8

        while bit_count >= 7:
            result.append(chr(current_byte & 0x7F))
            current_byte >>= 7
            bit_count -= 7

    return "".join(result)

if __name__ == "__main__":
    raw_store = open("com.apple.LaunchServices-3027-v2.csstore", "rb").read()
    store = CSStore.from_bytes(raw_store)

    for _, table in store.tables.items():
        if table.name == "PluginUUIDBinding":
            print(table.hashmap.map[8].data.hex())
            data = table.hashmap.map[8].data
            print(unpack_7bit(data))
            # Try to parse as 6-bit packed string
