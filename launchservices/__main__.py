import click
from .csstore import CSStore
from .lsdatabase import LSDatabase
from io import BytesIO

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
        click.echo(f"{d.tell() - 16:04x} ", nl=False)
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
            click.echo(click.style(f"{(key &~ 0x0F000000):02x}", fg="black"))
            break
        click.echo(click.style(f"{key:02x} ", fg="black"), nl=False)

    click.echo(f"Build:\t\t{h.read(0x10).decode("utf-8")}")
    click.echo(f"Model:\t\t{h.read(0x20).decode("utf-8")}")

if __name__ == "__main__":
    cli()