import factory
from factory.django import DjangoModelFactory

from scribe_store.models import ScribeSource, ScribeStore


class ScribeSouceFactory(DjangoModelFactory):
    class Meta:
        model = ScribeSource

    slug = factory.Sequence(lambda n: f"test-{n}")
    url = factory.LazyAttribute(lambda o: f"https://example.com/{o.slug}.csv")


class ScribeStoreFactory(DjangoModelFactory):
    class Meta:
        model = ScribeStore

    source = factory.SubFactory(ScribeSouceFactory)
    status = ScribeStore.Status.DOWNLOADED
    file = factory.django.FileField(filename="test.csv")
