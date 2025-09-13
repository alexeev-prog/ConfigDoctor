import click


@click.group()
def cli():
    """Software for quickly creating and building C/C++ projects."""


@cli.command()
@click.argument("target", nargs=-1, required=True)
def check(target: list):
    """Check and lint target dir or file."""


def main():
    """Main function."""
    cli()
