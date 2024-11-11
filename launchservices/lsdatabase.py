
from dataclasses import dataclass, field
from enum import IntFlag
from io import BytesIO
from typing import Self

from .csstore import CSStore, CSUnit

def unpack_string(data: int) -> str:
    packed_alphabet = '\x00 abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    return ''.join(packed_alphabet[(data >> (2 + 6 * i)) & 0x3f] for i in range(5)).rstrip('\x00')[::-1]

LSBinding = dict[str, list[str]]

@dataclass
class LSClaim(CSUnit):
    class Flags(IntFlag):
        APPLE_DEFAULT = 0x1
        APPLE_DEFAULT_NO_OVERRIDE = 0x2
        APPLE_INTERNAL = 0x4
        RELATIVE_ICON_PATH = 0x1000
        PACKAGE = 0x8
        LEGACY_WILDCARD = 0x10
        DOC_TYPE = 0x20
        URL_TYPE = 0x40
        PRIVATE_SCHEME = 0x80
        ALWAYS_AVAILABLE = 0x100
        RESOLVES_ICLOUD_CONFLICTS = 0x200
        UTI_WILDCARD = 0x400
        SUPPORTS_COLLABORATION = 0x800
    
    class Roles(IntFlag):
        NONE = 0x1
        VIEWER = 0x2
        EDITOR = 0x4
        SHELL = 0x8
        IMPORTER = 0x10
        QLGENERATOR = 0x20

    claiming_bundle: int
    generation: int
    claim_flags: "LSClaim.Flags"
    rank: int
    roles: "LSClaim.Roles"
    bundle: int
    localized_names: int
    req_caps: list[str]
    icon_files: list[str]
    delegate: str
    bindings: LSBinding

    @classmethod
    def from_unit(cls, unit: CSUnit, database: "LSDatabase") -> Self:
        d = BytesIO(unit.data)
        claiming_bundle_record = int.from_bytes(d.read(4), "little")
        generation = int.from_bytes(d.read(4), "little")
        
        flags = cls.Flags(int.from_bytes(d.read(4), "little"))
        rank = int.from_bytes(d.read(2), "little")
        roles = cls.Roles(int.from_bytes(d.read(2), "little"))

        bundle = int.from_bytes(d.read(4), "little")
        localized_names = int.from_bytes(d.read(4), "little")
        
        req_caps = database.get_string_array(int.from_bytes(d.read(4), "little"))

        icon_files = []
        for _ in range(9):
            i = int.from_bytes(d.read(4), "little")
            if i != 0 and i != 1:
                icon_files.append(database.store.strings.get_string(i))
        
        delegate = database.store.strings.get_string(int.from_bytes(d.read(4), "little"))
        if delegate != "":
            raise NotImplementedError("Delegate is not empty")
        bindings = database.binding_list[int.from_bytes(d.read(4), "little")]

        assert d.read() == b""

        return cls(unit.id, unit.flags, unit.data, claiming_bundle_record, generation, flags, rank, roles, bundle, localized_names, req_caps, icon_files, delegate, bindings)

@dataclass
class LSDatabase:
    store: CSStore
    schema: int = 0
    build: str = ""
    model: str = ""
    binding_list: dict[int, LSBinding] = field(default_factory=dict)

    def __post_init__(self):
        self.schema, self.build, self.model = self._parse_header()
        self.binding_list = self._get_binding_list()

    @classmethod
    def from_bytes(cls, data: bytes):
        store = CSStore.from_bytes(data)
        return cls(store)

    def _parse_header(self) -> tuple[int, str, str]:
        header = BytesIO(self.store.get_table("DB Header").extra)
        schema = int.from_bytes(header.read(4), "little")
        header_len = int.from_bytes(header.read(4), "little")
        while header.tell() < header_len:
            key = int.from_bytes(header.read(4), "little")
            assert int.from_bytes(header.read(4), "little") == 0x0
            if key & 0x0F000000 != 0:
                break
        build = header.read(0x10).decode("utf-8")
        model = header.read(0x20).decode("utf-8")
        return schema, build, model
    
    def _get_binding_list(self) -> dict[int, LSBinding]:
        binding_list = self.store.get_table("BindingList")
        out = {}
        for key, value in binding_list.hashmap.items():
            d = BytesIO(value.data)
            list_count = int.from_bytes(d.read(4), "little")
            out_inner = {}
            for _ in range(list_count):
                name = self.store.strings.get_string(int.from_bytes(d.read(4), "little"))
                value_count = int.from_bytes(d.read(4), "little")
                values = []
                for _ in range(value_count):
                    value = int.from_bytes(d.read(4), "little")
                    if value & 1:
                        value = unpack_string(value)
                    else:
                        value = self.store.strings.get_string(value)
                    values.append(value)
                out_inner[name] = values
            out[key] = out_inner
        return out
    
    def get_claims(self):
        claims = self.store.get_table("Claim")
        out = {}

        for key, value in claims.hashmap.items():
            if value.data == b"":
                out[key] = None
                continue
            out[key] = LSClaim.from_unit(value, self)

        return out

    def get_string_array(self, key: int) -> list[str]:
        if key != 0:
            raise NotImplementedError("<array> never tested")
        return [self.store.strings.get_string(x) for x in self.store.get_array(key)]

            
