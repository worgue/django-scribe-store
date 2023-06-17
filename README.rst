=======================
django-scribe-store
=======================

``django-scribe-store`` is a Django module to download file via HTTP and execute data insertion.
This module assures storing downloaded file and helps with tracing
the correspondence between loaded data rows and the destination instances.

Key Features
------------

- Downloads and stores CSV files
- Loads CSV data and saves it to the database
- Maps loaded CSV rows to the target model

Installation
------------
pip:

.. code-block:: sh

    $ pip install django-scribe-store

Add ``scribe_store`` to ``INSTALLED_APPS``:

.. code-block:: python

    # settings.py
    INSTALLED_APPS = (
        ...
        'scribe_store',
    )

migrate:

.. code-block:: sh

    $ python manage.py migrate

Usage
-----

A simple example to use this module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Create the target model.

.. code-block:: python

    # sample/models.py
    class Question(models.Model):
        question_text = models.CharField(max_length=200)
        pub_date = models.DateTimeField("date published")

2. Publish the csv file corresponding to the model.

e.g) publish: ``https://example.com/question/simple.csv``:

::

    question_text,pub_date
    Is this a question?,2023-06-12
    How is the date converted?,2023-06-13
    How are empty rows processed?,2023-06-14

3. Create ``ScribeSource`` and run ``scribe`` method:

.. code-block:: python

    from sample.models import Question
    from scribe_store.models import ScribeSource

    # Checking the initial state
    Question.objects.count()  # o/p 0

    # Setting up the data source
    source_simple = ScribeSource.objects.create(
        slug="simple",
        url="https://example.com/question/simple.csv",
        target=ContentType.objects.get(model="question"),
    )

    # Scribing the data
    source_simple.scribe()

    # Checking the resulting data
    Question.objects.count()  # o/p 3

4. You can access the downloaded file:

.. code-block:: python

    store = source_simple.store_set.get()
    with open(dd.file.path) as fp:
        print(fp.read())
    # o/p
    # question_text,pub_date
    # Is this a question?,2023-06-12
    # How is the date converted?,2023-06-13
    # How are empty rows processed?,2023-06-14

5. It is also possible to check created data:

.. code-block:: python

    store.created().count()  # o/p 3
    store.created().model  # o/p <class 'sample.models.Question'>

Some other features
~~~~~~~~~~~~~~~~~~~

Header with name
""""""""""""""""

In the CSV header, you can also use the names defined in the model.

e.g) publish: ``https://example.com/question/nameheader.csv``:

::

    question_text,date published
    Is this another question?,2023-06-15

Then:

.. code-block:: python

    Question.objects.count()  # o/p 3
    source_nameheader = ScribeSource.create(
        name="nameheader",
        url="https://example.com/question/nameheader.csv",
        target=ContentType.objects.get(model="question"),
    )
    source_nameheader.scribe()
    Question.objects.count()  # o/p 4

Fetch data multiple times
"""""""""""""""""""""""""

You can re-fetch the data from the same URL. Even if the CSV is updated, you can keep a log of the data:

.. code-block:: python

    source_simple.scribe()
    source_simple.store_set.count()  # o/p 2

Format url using strftime
"""""""""""""""""""""""""

To utilize this feature, you can use timeformat url.
You can download from url like these according to the current local time:

- https://example.com/20230614-08
- https://example.com/20230614-20
- https://example.com/20230615-08

.. code-block:: python

    # strftime is called with localtime
    timezone.localtime()  # o/p datetime.datetime(2023, 6, 14, 8, 0, 0, 123456, tzinfo=zoneinfo.ZoneInfo(key='Asia/Tokyo'))

    source_strftime = ScribeSource.objects.create(
        slug="strftime",
        url="https://example.com/%Y%m%d-%H",
        target=ContentType.objects.get(model="question"),
    )
    source_strftime.scribe()
    source_strftime.store_set.get().url  # o/p https://example.com/20230614-08

Rollback
""""""""

If error occurs while loading, all insertion steps will be rollbacked.
For example, create new model ``News`` which has unique slug:

.. code-block:: python
    class News(models.Model):
        slug = models.SlugField(unique=True)
        news_text = models.CharField(max_length=200)
        pub_date = models.DateTimeField("date published")

And create csv file which cause ``django.db.utils.IntegrityError`` about unique constraint.

e.g) publish: ``https://example.com/news/uniqueinvalid.csv``:

::

    slug,news_text,pub_date
    hello-world,"Hello, world!",2023-06-12
    hello-world,"Hello, world 2!",2023-06-13
    hello-world-3,"Hello, world 3!",2023-06-14

Then:

.. code-block:: python

    from sample.models import News

    source_uniqueinvalid = ScribeSource.objects.create(
        slug="uniqueinvalid",
        url="https://example.com/news/uniqueinvalid.csv",
        target=ContentType.objects.get(model="news"),
    )
    source_uniqueinvalid.scribe()
    # django.db.utils.IntegrityError: UNIQUE constraint failed: sample_news.slug

    # As all process is in transaction, you will get no News.
    News.objects.count()  # o/p 0

Customize data loading process
""""""""""""""""""""""""""""""

You can deal with such situations by creating custom data load method in the model's manager:

.. code-block:: python

    class NewsBManager(models.Manager):
        def scribe_dict(self, data):
            if self.filter(slug=data["slug"]).exists():
                return
            return self.create(**data)


    class NewsB(models.Model):
        slug = models.SlugField(unique=True)
        news_text = models.CharField(max_length=200)
        pub_date = models.DateTimeField("date published")

        objects = NewsBManager()

Then:

.. code-block:: python

    from sample.models import NewsB

    NewsB.objects.count()  # o/p 0
    source_uniqueinvalid = ScribeSource.objects.create(
        slug="uniqueinvalid",
        url="https://example.com/news/uniqueinvalid.csv",
        target=ContentType.objects.get(model="newsb"),
    )
    source_uniqueinvalid.scribe()
    NewsB.objects.count()  # o/p 2
    # check created data
    store = source_uniqueinvalid.store_set.get()
    store.created().count()  # o/p 2


Check other status of data
""""""""""""""""""""""""""

You can trace not only created, but also updated, deleted, and unknown by returning ``RowStatus``:

.. code-block:: python

    from scribe_store import RowStatus

    class NewsCManager(models.Manager):
        def scribe_dict(self, data):
            if self.filter(slug=data["slug"]).exists():
                news = self.filter(slug=data["slug"]).exists()
                news.news_text = data["news_text"]
                news.save()
                return news, RowStatus.UPDATED
            return self.create(**data)

    class NewsC(models.Model):
        slug = models.SlugField(unique=True)
        news_text = models.CharField(max_length=200)
        pub_date = models.DateTimeField("date published")

        objects = NewsCManager()

Then:

.. code-block:: python

    from sample.models import NewsC

    NewsC.objects.count()  # o/p 0
    source_uniqueinvalid = ScribeSource.objects.create(
        slug="uniqueinvalid",
        url="https://example.com/news/uniqueinvalid.csv",
        target=ContentType.objects.get(model="newsc"),
    )
    source_uniqueinvalid.scribe()
    NewsC.objects.count()  # o/p 2
    store = source_uniqueinvalid.store_set.get()
    store.crated().count()  # o/p 2
    store.updated().count()  # o/p 1
    store.related().count()  # o/p 2

Delete created data
"""""""""""""""""""

You can delete newly created data:

e.g) publish: ``https://example.com/news/1update2create.csv``:

::

    slug,news_text,pub_date
    hello-world,"Update!",2023-06-12
    hello-new-world-1,"Create!",2023-06-13
    hello-new-world-2,"Create!",2023-06-14

.. code-block:: python
    NewsC.objects.count()  # o/p 2
    # scribe above csv additionally
    source_1update2create = ScribeSource.objects.create(
        slug="uniqueinvalid",
        url="https://example.com/news/1update2create.csv",
        target=ContentType.objects.get(model="newsc"),
    )
    source_1update2create.scribe()
    store = source_1update2create.store_set.get()
    store.crated().count()  # o/p 2
    store.updated().count()  # o/p 1
    store.related().count()  # o/p 3
    NewsC.objects.count()  # o/p 4
    store.delete_created()
    NewsC.objects.count()  # o/p 2

But this function doesn't concern about update.
If you set RowStatus.UPDATE, ``delete_created`` just ignore the instances.
Moreover, ``delete_created`` delete the data created by the store, even if the data was updated by other way.
Be careful to use it.


Management commands
~~~~~~~~~~~~~~~~~~~

There are some management commands.
You can easily load data periodically with task management tools, like cron, celery, etc...

scribe_new
""""""""""

Add new ScribeSource entry and load data.

.. code-block:: sh

    $ python manage.py scribe_new simple-question https://example.com/question/simple.csv question

.. code-block:: python

    >>> ScribeSource.objects.count()
    1
    >>> ScribeStore.objects.count()
    1
    >>> Question.objects.count()
    3

You can reuse ScribeSource by the slug:

.. code-block:: sh

    $ python manage.py scribe simple-question

``scribe_new`` has ``--entry-only`` options, and ``scribe`` has ``--download-only``, ``--use-downloaded`` and ``--downloaded-slug`` options.
By using these options, you can proceed data import procedure step by step.
And you can check the data through django admin site.

Django admin site
~~~~~~~~~~~~~~~~~

You can check the information through admin site.

Jump to related data from scribe_store's ScribeRow list
"""""""""""""""""""""""""""""""""""""""""""""""""""""""

.. image:: https://github.com/worgue/django-scribe-store/blob/main/docs/images/admin_screenshot_scriberow_list.png
    :width: 500
    :alt: Admin screenshot of ScribeRow list

Check accepted data in the ScribeRow detail
"""""""""""""""""""""""""""""""""""""""""""

.. image:: https://github.com/worgue/django-scribe-store/blob/main/docs/images/admin_screenshot_scriberow_detail.png
    :width: 500
    :alt: Admin screenshot of ScribeRow detail

Reversely you can check ``scribe_store`` data from you own model, using ``ScribeAdminMixin``:

.. code-block:: python

    # sample/admin.py
    from scribe_store.admin import ScribeAdminMixin
    from .models import Question

    @admin.register(Question)
    class QuestionAdmin(ScribeAdminMixin, admin.ModelAdmin):
        list_display = ["question_text", "pub_date"]

Jump to scribe_store model's from sample Question list
""""""""""""""""""""""""""""""""""""""""""""""""""""""

.. image:: https://github.com/worgue/django-scribe-store/blob/main/docs/images/admin_screenshot_question_list.png
    :width: 500
    :alt: Admin screenshot of Question list

Check accepted data in the Question detail
""""""""""""""""""""""""""""""""""""""""""

.. image:: https://github.com/worgue/django-scribe-store/blob/main/docs/images/admin_screenshot_question_detail.png
    :width: 500
    :alt: Admin screenshot of Question detail


Settings
--------

You can configure the following in your settings file:

``SCRIBE_STORE_STRIP_VALUE``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Controls if the imported data is stripped. ``value.strip()`` will be called.
Defaults to ``True``.
