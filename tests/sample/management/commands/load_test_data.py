import djclick as click
from django.contrib.contenttypes.models import ContentType
from sample.factories import ScribeStoreFactory
from sample.models import News

from ...models import Question


@click.command()
def command():
    store_news = ScribeStoreFactory.create(
        source__target=ContentType.objects.get_for_model(News),
        file__from_path="sample/data/news/simple.csv",
    )
    store_question = ScribeStoreFactory.create(
        source__target=ContentType.objects.get_for_model(Question),
        file__from_path="sample/data/question/simple.csv",
    )
    store_news.load_csv()
    store_question.load_csv()
