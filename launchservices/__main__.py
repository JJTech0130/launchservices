import click
from .csstore import CSStore, CSTable
from .lsdatabase import LSDatabase
from io import BytesIO

@click.group()
#@click.pass_context
def csstore():
    pass

@csstore.command()
@click.argument("store_path")
def create(store_path: str):
    store = CSStore()
    #table = CSTable("")
    #store.tables.append(table)
    print(store)

    with open(store_path, "wb") as f:
        f.write(store.to_bytes())

@csstore.command()
@click.argument("store_path")
@click.argument("dump_path")
def dump(store_path: str, dump_path: str):
    raw_store = open(store_path, "rb").read()
    store = CSStore.from_bytes(raw_store)
    with open(dump_path, "w") as f:
        import pprint
        pprint.pprint(store, f, width=800)

@click.group()
@click.argument("store_path")
@click.pass_context
def lsdb(ctx, store_path: str):
    raw_store = open(store_path, "rb").read()
    store = CSStore.from_bytes(raw_store)
    database = LSDatabase(store=store)
    ctx.obj = database

def hexdump(b: bytes):
    d = BytesIO(b)
    def _format_byte(b: int) -> str:
        return f"{b:02x}" if b != 0 else click.style("00", fg="black")
    while True:
        chunk = d.read(16)
        if not chunk:
            break
        click.echo(f"{d.tell() - 16:04x} ", nl=False)
        click.echo(" ".join(_format_byte(x) for x in chunk) + " ", nl=False)
        click.echo("".join(chr(x) if 32 <= x < 127 else click.style(".", "black") for x in chunk), nl=True)

@lsdb.command()
@click.pass_context
def header(ctx):
    database: LSDatabase = ctx.obj

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
            click.echo(click.style(f"{(key &~ 0x0F000000):02x}", fg="black"))
            break
        click.echo(click.style(f"{key:02x} ", fg="black"), nl=False)

    click.echo(f"Build:\t\t{h.read(0x10).decode("utf-8")}")
    click.echo(f"Model:\t\t{h.read(0x20).decode("utf-8")}")

@lsdb.command()
@click.pass_context
def claims(ctx):
    database: LSDatabase = ctx.obj
    assert "iPhone" in database.model

    claims = database.get_claims()
    for key, value in claims.items():
        click.echo(f"{key:04x}: {value}")

if __name__ == "__main__":
    lsdb()