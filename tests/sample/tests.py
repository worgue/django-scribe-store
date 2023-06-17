import click
import responses
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db.utils import IntegrityError
from django.test import TestCase, override_settings
from django.utils import timezone
from freezegun import freeze_time
from sample.models import News, NewsB, NewsC, Question

from scribe_store.models import (
    BadHttpStatusException,
    ScribeRow,
    ScribeSource,
    ScribeStore,
)


class ScribeTest(TestCase):
    def test_something(self):
        self.assertEqual(True, True)

    def test_question_model(self):
        self.assertEqual(Question.objects.count(), 0)
        Question.objects.create(
            question_text="What is the meaning of life?",
            pub_date=timezone.now(),
        )
        self.assertEqual(Question.objects.count(), 1)

    @responses.activate
    def test_http_exception(self):
        responses.add(
            responses.GET,
            "https://example.com/error-403",
            status=403,
        )
        with self.assertRaises(BadHttpStatusException):
            source = ScribeSource.objects.create(
                slug="sample-slug",
                url="https://example.com/error-403",
                target=ContentType.objects.get(model="question"),
            )
            source.scribe()

    def add_rewponses(self, category, key):
        with open("sample/data/%s/%s.csv" % (category, key), "rb") as fp:
            responses.add(
                responses.GET,
                "https://example.com/data",
                body=fp.read(),
                content_type="text/plain",
                status=200,
            )

    def get_source(self, category, key, target_name=None):
        if target_name is None:
            target_name = category
        ct = ContentType.objects.get(model=target_name)
        self.add_rewponses(category, key)
        source = ScribeSource.objects.create(
            slug=key, url="https://example.com/data", target=ct
        )
        return source

    def scribe_sample_question(self, key, target_name=None):
        source = self.get_source("question", key, target_name)
        source.scribe()
        return source

    def scribe_sample_news(self, key, target_name=None):
        source = self.get_source("news", key, target_name)
        source.scribe()
        return source

    @responses.activate
    def test_question_simple(self):
        self.assertEqual(Question.objects.count(), 0)
        self.scribe_sample_question("simple")
        self.assertEqual(Question.objects.count(), 3)

    @responses.activate
    def test_question_simple_twice(self):
        self.assertEqual(ScribeSource.objects.count(), 0)
        self.assertEqual(ScribeStore.objects.count(), 0)
        self.assertEqual(ScribeRow.objects.count(), 0)
        self.assertEqual(Question.objects.count(), 0)
        source = self.scribe_sample_question("simple")
        self.assertEqual(ScribeSource.objects.count(), 1)
        self.assertEqual(ScribeStore.objects.count(), 1)
        self.assertEqual(ScribeRow.objects.count(), 3)
        self.assertEqual(Question.objects.count(), 3)
        source.scribe()
        self.assertEqual(ScribeSource.objects.count(), 1)
        self.assertEqual(ScribeStore.objects.count(), 2)
        self.assertEqual(ScribeRow.objects.count(), 6)
        self.assertEqual(Question.objects.count(), 6)

    @freeze_time("2023-06-13 23:00:00")  # freeze as utc
    @responses.activate
    def test_strftime(self):
        formatted_url = timezone.localtime().strftime("https://example.com/%Y%m%d-%H")
        self.assertEqual(formatted_url, "https://example.com/20230614-08")
        self.assertEqual(Question.objects.count(), 0)
        ct = ContentType.objects.get(model="question")
        with open("sample/data/question/simple.csv") as fp:
            responses.add(
                responses.GET,
                formatted_url,
                body=fp.read(),
                content_type="text/plain",
                status=200,
            )
        source = ScribeSource.objects.create(
            slug="strftime", url="https://example.com/%Y%m%d-%H", target=ct
        )
        source.scribe()
        self.assertEqual(Question.objects.count(), 3)
        self.assertEqual(source.store_set.get().url, "https://example.com/20230614-08")

    @responses.activate
    def test_question_spaces(self):
        self.scribe_sample_question("spaces")
        self.assertEqual(
            Question.objects.get().question_text,
            "Is this a question?",
        )

    @override_settings(SCRIBE_STORE_STRIP_VALUE=False)
    @responses.activate
    def test_question_spaces(self):
        self.scribe_sample_question("spaces")
        self.assertEqual(
            Question.objects.get().question_text,
            "Is this a question? ",
        )

    @responses.activate
    def test_question_emptylines(self):
        self.scribe_sample_question("emptylines")
        self.assertEqual(
            Question.objects.get().question_text,
            "Is this a question?",
        )

    @responses.activate
    def test_question_nameheader(self):
        self.scribe_sample_question("nameheader")
        self.assertEqual(Question.objects.count(), 3)

    @responses.activate
    def test_news_simple(self):
        self.assertEqual(News.objects.count(), 0)
        self.scribe_sample_news("simple")
        self.assertEqual(News.objects.count(), 3)

    @responses.activate
    def test_news_uniqueinvalid(self):
        self.assertEqual(News.objects.count(), 0)
        with self.assertRaises(IntegrityError):
            self.scribe_sample_news("uniqueinvalid")
        self.assertEqual(News.objects.count(), 0)

    @responses.activate
    def test_ignore_exists(self):
        self.assertEqual(NewsB.objects.count(), 0)
        source = self.get_source("news", "uniqueinvalid", "newsb")
        source.scribe()
        self.assertEqual(NewsB.objects.count(), 2)

    @responses.activate
    def test_update_exists(self):
        self.assertEqual(NewsC.objects.count(), 0)
        source = self.get_source("news", "uniqueinvalid", "newsc")
        source.scribe()
        self.assertEqual(NewsC.objects.count(), 2)
        store = source.store_set.get()
        self.assertEqual(store.created().count(), 2)
        self.assertEqual(store.updated().count(), 1)
        self.assertEqual(store.related().count(), 2)

    @responses.activate
    def test_delete_created(self):
        self.scribe_sample_news("uniqueinvalid", "newsc")
        self.assertEqual(NewsC.objects.count(), 2)
        self.assertEqual(NewsC.objects.count(), 2)
        source = self.get_source("news", "1update2create", "newsc")
        source.scribe()
        store = source.store_set.get()
        self.assertEqual(store.created().count(), 2)
        self.assertEqual(store.updated().count(), 1)
        self.assertEqual(store.related().count(), 3)
        self.assertEqual(NewsC.objects.count(), 4)
        store.delete_created()
        self.assertEqual(NewsC.objects.count(), 2)

    @responses.activate
    def test_command_scribe_new(self):
        self.add_rewponses("question", "simple")
        call_command(
            "scribe_new", "simple-question", "https://example.com/data", "question"
        )
        self.assertEqual(ScribeSource.objects.count(), 1)
        self.assertEqual(ScribeStore.objects.count(), 1)
        self.assertEqual(Question.objects.count(), 3)

    @responses.activate
    def test_command_scribe_new_entry_only(self):
        self.add_rewponses("question", "simple")
        call_command(
            "scribe_new",
            "simple-question",
            "https://example.com/data",
            "question",
            entry_only=True,
        )
        self.assertEqual(ScribeSource.objects.count(), 1)
        self.assertEqual(ScribeStore.objects.count(), 0)
        self.assertEqual(Question.objects.count(), 0)

    @responses.activate
    def test_command_scribe(self):
        self.add_rewponses("question", "simple")
        call_command(
            "scribe_new",
            "simple-question",
            "https://example.com/data",
            "question",
            entry_only=True,
        )
        call_command("scribe", "simple-question")
        self.assertEqual(ScribeSource.objects.count(), 1)
        self.assertEqual(ScribeStore.objects.count(), 1)
        self.assertEqual(Question.objects.count(), 3)

    @responses.activate
    def test_command_scribe_options(self):
        self.add_rewponses("question", "simple")
        call_command(
            "scribe_new",
            "simple-question",
            "https://example.com/data",
            "question",
            entry_only=True,
        )
        call_command("scribe", "simple-question", download_only=True)
        self.assertEqual(ScribeSource.objects.count(), 1)
        self.assertEqual(ScribeStore.objects.count(), 1)
        self.assertEqual(Question.objects.count(), 0)
        store_1 = ScribeStore.objects.get()
        self.assertEqual(store_1.status, store_1.Status.DOWNLOADED)
        call_command("scribe", "simple-question", download_only=True)
        self.assertEqual(ScribeSource.objects.count(), 1)
        self.assertEqual(ScribeStore.objects.count(), 2)
        self.assertEqual(Question.objects.count(), 0)
        call_command("scribe", "simple-question", use_downloaded=True)
        self.assertEqual(ScribeSource.objects.count(), 1)
        self.assertEqual(ScribeStore.objects.count(), 2)
        self.assertEqual(Question.objects.count(), 3)
        with self.assertRaises(click.ClickException):
            call_command("scribe", "simple-question", use_downloaded=True)
        self.assertEqual(ScribeSource.objects.count(), 1)
        self.assertEqual(ScribeStore.objects.count(), 2)
        self.assertEqual(Question.objects.count(), 3)
        call_command(
            "scribe",
            "simple-question",
            use_downloaded=True,
            downloaded_slug=store_1.slug,
        )
        self.assertEqual(ScribeSource.objects.count(), 1)
        self.assertEqual(ScribeStore.objects.count(), 2)
        self.assertEqual(Question.objects.count(), 6)
        store_1.refresh_from_db()
        self.assertEqual(store_1.status, store_1.Status.COMPLETED)
