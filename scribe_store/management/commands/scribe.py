import djclick as click

from scribe_store import RowStatus
from scribe_store.models import ScribeSource


def validate_use_downloaded(ctx, param, value):
    if value and ctx.params.get("download_only"):
        raise click.BadParameter("use-downloaded and download-only are exclusive.")
    return value


def validate_slug(ctx, param, value):
    if value and not ctx.params.get("use_downloaded"):
        raise click.BadParameter("downloaded-slug is valid only with use-downloaded.")
    return value


@click.command()
@click.argument("scribe_source_slug")
@click.option("--download-only", is_flag=True, default=False, help="Download only.")
@click.option(
    "--use-downloaded",
    is_flag=True,
    default=False,
    callback=validate_use_downloaded,
    help="Use already downloaded data(latest). You can specify slug with --downloaded-slug.",
)
@click.option("--downloaded-slug", callback=validate_slug, help="Slug of OuterData.")
def command(scribe_source_slug, download_only, use_downloaded, downloaded_slug):
    """Download outer data and save to target."""
    source = ScribeSource.objects.get(slug=scribe_source_slug)
    if not use_downloaded:
        source.fetch()
    if download_only:
        return
    if downloaded_slug:
        store = source.store_set.get(slug=downloaded_slug)
    else:
        store = source.store_set.latest("downloaded_at")
    if store.status == store.Status.COMPLETED:
        raise click.ClickException("Already loaded.")
    store.load_file()
