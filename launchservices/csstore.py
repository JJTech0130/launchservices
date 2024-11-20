from io import BytesIO
from typing import Self
from dataclasses import dataclass, field

FLAG_CATALOG = 0x40000000
ALL_FLAGS = FLAG_CATALOG

@dataclass(kw_only=True)
class CSUnit:
    #id: int
    flags: int = 0
    _data: bytes = b""

    @classmethod
    def from_stream(cls, d: BytesIO) -> Self:
        id_and_flags = int.from_bytes(d.read(4), "little")
        id = (id_and_flags &~ ALL_FLAGS) << 2
        #print("read id", id)
        flags = id_and_flags & ALL_FLAGS
        size = int.from_bytes(d.read(4), "little")
        data = d.read(size)
        return cls(flags=flags, _data=data)
    
    @property
    def data(self) -> bytes:
        return self._data
    
    def to_stream(self, o: BytesIO, id: int):
        id_and_flags = (id >> 2) | self.flags
        b = id_and_flags.to_bytes(4, "little") + len(self._data).to_bytes(4, "little") + self._data
        o.write(b)
    
def hashmap_from_stream(d: BytesIO, start: int) -> dict:
    map = {}
    tell = d.tell()
    d.seek(start)
    bucket_count = int.from_bytes(d.read(4), "little")
    print("Bucket count", bucket_count)
    for _ in range(bucket_count):
        item_count = int.from_bytes(d.read(4), "little")
        items_offset = int.from_bytes(d.read(4), "little")
        t = d.tell()
        #print(f"{item_count} items at {items_offset}")
        d.seek(items_offset)
        for _ in range(item_count):
            key = int.from_bytes(d.read(4), "little")
            v = int.from_bytes(d.read(4), "little")

            map[key] = v
        d.seek(t)
    d.seek(tell)
    return map

def hashmap_to_stream(d: BytesIO, map: dict):
    # need to write buckets 0 to 1024 if empty, otherwise, need 1 bucket per key?
    start = d.tell()
    d.write((1024).to_bytes(4, "little"))
    end_buckets = d.tell() + 1024 * 8
    for i in range(1024):
        d.write((1).to_bytes(4, "little"))
        d.write((end_buckets + i * 8).to_bytes(4, "little"))
    assert d.tell() == end_buckets
    # Write empty buckets
    for i in range(1024):
        d.write((0).to_bytes(4, "little")) # key
        d.write((0xFFFFFFFF).to_bytes(4, "little")) # value
    

    # start = d.tell()
    # d.write(len(map).to_bytes(4, "little"))
    # for key, value in map.items():
    #     d.write(1)
    #     d.write(key.to_bytes(4, "little"))
    #     d.write(value.to_bytes(4, "little"))
    # return start
@dataclass
class CSTable(CSUnit):
    name: str
    _next_unit_id: int = 0
    extra: bytes = b""
    hashmap: dict[int, CSUnit] = field(default_factory=dict)

    @property
    def data(self) -> bytes:
        raise NotImplementedError("Cannot get data from table")
    
    @classmethod
    def from_unit(cls, unit: CSUnit, d: BytesIO) -> Self:
        da = BytesIO(unit.data)
        name = da.read(0x30).strip(b"\x00").decode("utf-8")
        da.read(0x10)
        next_unit_id = int.from_bytes(da.read(4), "little") * 4
        hashmap_header_start = int.from_bytes(da.read(4), "little")
        extra = da.read()
        if hashmap_header_start != 0:
            hashmap = hashmap_from_stream(d, hashmap_header_start)
            for key, value in hashmap.items():
                d.seek(value)
                hashmap[key] = CSUnit.from_stream(d)
        else:
            hashmap = {}
        return cls(name=name, _next_unit_id=next_unit_id, extra=extra, hashmap=hashmap)
    
    def store_unit(self, unit: CSUnit) -> int:
        uid = self._next_unit_id
        self.hashmap[uid] = unit
        self._next_unit_id += 4
        return uid
    
    def to_stream(self, o: BytesIO, id: int):
        # First create the unit contents
        da = BytesIO()
        da.write(self.name.encode("utf-8"))
        da.write(b"\x00" * (0x30 - len(self.name)))
        da.write(b"\x00" * 0x10)
        da.write((self._next_unit_id // 4).to_bytes(4, "little"))
        da.write((0).to_bytes(4, "little"))
        da.write(self.extra)
        # TODO: Write hashmap
        da = bytearray(da.getvalue())
        print(da.hex())
        # Create the unit
        u = CSUnit(flags=FLAG_CATALOG if self.name == "<catalog>" else 0, _data=da)
        address_to_write_start = o.tell() + 0x30 + 0x10 + 0x4 + 0x8 # TODO: Better way to get this?
        u.to_stream(o, id)

        hashmap_header_start = o.tell()
        o.seek(address_to_write_start)
        o.write(hashmap_header_start.to_bytes(4, "little"))
        o.seek(hashmap_header_start)
        hashmap_to_stream(o, self.hashmap)
        

@dataclass(kw_only=True)
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
        return cls(_strings=s, _refcnt=refcnt)
    
    def get_string(self, key: int) -> str:
        return self._strings.hashmap[key].data.decode("utf-8")
    
    def retain_string(self, key: int):
        self._refcnt[key] += 1
    
    def release_string(self, key: int):
        self._refcnt[key] -= 1
        if self._refcnt[key] == 0:
            del self._refcnt[key]

    def store_string(self, s: str) -> int:
        key = self._strings.store_unit(CSUnit(_data=s.encode("utf-8")))
        self._refcnt[key] = 1
        return key

@dataclass(kw_only=True)
class CSStore:
    magic = b"bdsl"
    version = 2
    tables: list[CSTable] = field(default_factory=list)
    _strings: CSStringContainer | None = None

    @classmethod
    def from_bytes(cls, data: bytes):
        d = BytesIO(data)

        # Header
        assert d.read(4) == cls.magic
        assert d.read(1) == cls.version.to_bytes(1, "little")
        d.read(1)
        _crc = int.from_bytes(d.read(2), "little")
        d.read(4)
        _size1 = int.from_bytes(d.read(4), "little")
        _size2 = int.from_bytes(d.read(4), "little")

        catalog = CSUnit.from_stream(d)
        assert catalog.flags & FLAG_CATALOG
        catalog = CSTable.from_unit(catalog, d)

        tables = []
        strings = None

        for key, value in catalog.hashmap.items():
            table = CSTable.from_unit(value, d)
            if table.name == "<string>":
                strings = CSStringContainer.from_store(table, d)
                continue
            else:
                tables.append(table)
                #tables[key] = table

        #assert strings

        return cls(_strings=strings, tables=tables)
    
    def to_bytes(self) -> bytes:
        o = BytesIO()
        o.write(self.magic)
        o.write(self.version.to_bytes(2, "little"))
        o.write(b"\x00\x00") # CRC
        o.write((1).to_bytes(4, "little")) # ?
        sizes = o.tell()
        o.write((0).to_bytes(4, "little")) # Size 1
        o.write((0).to_bytes(4, "little")) # Size 2

        catalog = CSTable(name="<catalog>")
        for table in self.tables:
            #catalog.store_unit(CSUnit(flags=0))
            catalog.store_unit(table)
        if self._strings:
            catalog.store_unit(CSUnit(flags=0))
        
        catalog.to_stream(o, 0xFFFF6D74)

        # Write the sizes
        size = o.tell()
        o.seek(sizes)
        o.write(size.to_bytes(4, "little"))
        o.write(size.to_bytes(4, "little"))

        o.seek(0, 2)

        # Bring the file out to at least 0x8000
        while o.tell() < 0x8000:
            o.write(b"\x00")

        return o.getvalue()

    @property
    def strings(self) -> CSStringContainer:
        if not self._strings:
            self._strings = CSStringContainer(_strings=CSTable(name="<string>"), _refcnt={})
        return self._strings
    
    def get_table(self, name: str) -> CSTable:
        for table in self.tables:
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