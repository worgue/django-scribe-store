import djclick as click
from django.contrib.contenttypes.models import ContentType

from scribe_store import RowStatus
from scribe_store.models import ScribeSource


@click.command()
@click.argument("scribe_source_slug")
@click.argument("url")
@click.argument("target_model")
@click.option("--app-label", help="Explicitly set target model's app.")
@click.option(
    "--entry-only", is_flag=True, default=False, help="Only create ScribeSource."
)
def command(scribe_source_slug, url, target_model, app_label, entry_only):
    """
    Create new source SCRIBE_SOURCE_SLUG and downloaded data from URL and load data to TARGET_MODEL.
    You can specify TARGET_MODEL by lowercase model name.
    It's using django ContentType.
    If model name conflicts with other app, use --app-label option.
    """
    data_source = ScribeSource.objects.create(
        slug=scribe_source_slug,
        url=url,
        target=ContentType.objects.get(model=target_model),
    )
    if not entry_only:
        data_source.scribe()
