import csv
import json
import secrets
from functools import cached_property

import requests
from django.conf import settings
from django.contrib import admin
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

from . import RowStatus


class BadHttpStatusException(Exception):
    pass


class ScribeException(Exception):
    pass


class ScribeSource(models.Model):
    class DataType(models.TextChoices):
        CSV = "C", "CSV"

    slug = models.SlugField(unique=True)
    data_type = models.CharField(max_length=1, choices=DataType.choices, default="C")
    url = models.CharField(
        max_length=100,
        help_text="You can use strftime format. ex) https://example.com/%Y/%m/%d/",
    )
    target = models.ForeignKey(
        ContentType, blank=True, null=True, on_delete=models.SET_NULL
    )

    def __str__(self):
        return self.slug

    @property
    def current_url(self):
        return timezone.localtime().strftime(self.url)

    def fetch(self):
        data_url = self.current_url
        response = requests.get(data_url)
        if response.status_code != 200:
            raise BadHttpStatusException("status code: %s" % response.status_code)
        store = ScribeStore(source=self, url=data_url)
        store.ensure_slug()
        store.file.save(
            "%s/%s" % (self.slug, store.slug),
            ContentFile(response.content),
        )

    def scribe(self):
        self.fetch()
        self.store_set.latest("downloaded_at").load_file()


class ScribeStore(models.Model):
    class Status(models.TextChoices):
        DOWNLOADED = "D", "Downloaded"
        LOADING = "L", "Loading"
        COMPLETED = "C", "Completed"
        DELETED = "X", "Deleted"

    source = models.ForeignKey(
        ScribeSource, on_delete=models.CASCADE, related_name="store_set"
    )
    slug = models.SlugField(unique=True)
    url = models.URLField()
    file = models.FileField(upload_to="scribe-store/store")
    status = models.CharField(max_length=1, choices=Status.choices, default="D")
    downloaded_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.slug

    def save(self, *args, **kwargs):
        self.ensure_slug()
        return super().save(*args, **kwargs)

    def ensure_slug(self):
        if not self.slug:
            self.slug = secrets.token_hex(8)

    @cached_property
    def ModelClass(self):
        return self.source.target.model_class()

    @cached_property
    def header(self):
        with open(self.file.path) as csvfile:
            reader = csv.reader(csvfile)
            return next(reader)

    @cached_property
    def row_fields(self):
        row_fields = []
        field_names = {f.name for f in self.ModelClass._meta.fields}
        verbose_name_to_name = {
            f.verbose_name: f.name for f in self.ModelClass._meta.fields
        }
        for s in self.header:
            if s in field_names:
                row_fields.append(s)
            elif s in verbose_name_to_name:
                row_fields.append(verbose_name_to_name[s])
            else:
                row_fields.append(s)
        return row_fields

    def load_file(self):
        self.status = self.Status.LOADING
        self.save()
        if self.source.data_type == self.source.DataType.CSV:
            self.load_csv()
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save()

    def load_csv(self):
        with open(self.file.path) as csvfile:
            _ = next(csvfile)
            reader = csv.reader(csvfile)
            with transaction.atomic():
                for i, row in enumerate(reader):
                    self.load_row(i + 1, row)

    def load_row(self, object_index, row):
        if getattr(settings, "SCRIBE_STORE_STRIP_VALUE", True):
            row = [f.strip() for f in row]
        if not any(row):
            return
        data = dict(zip(self.row_fields, row))

        if hasattr(self.ModelClass.objects, "scribe_dict"):
            res = self.ModelClass.objects.scribe_dict(data)
            if res is None:
                ins = None
                status = RowStatus.IGNORED
            elif isinstance(res, self.ModelClass):
                ins = res
                status = RowStatus.CREATED
            elif type(res) is tuple:
                if len(res) != 2:
                    raise ScribeException(
                        "scribe_dict should return: None, object or 2 length tuple."
                    )
                ins, status = res
                if not isinstance(ins, self.ModelClass):
                    raise ScribeException(
                        "%s should be instance of %s" % (ins, self.ModelClass)
                    )
                if not status in RowStatus.values:
                    raise ScribeException(
                        "status should be RowStatus values. One of %s."
                        % (status, RowStatus.values)
                    )
        else:
            ins = self.ModelClass.objects.create(**data)
            status = RowStatus.CREATED
        ScribeRow.objects.create(
            store=self,
            object_index=object_index,
            data=json.dumps(data),
            status=status,
            target=ins,
        )

    def related(self):
        ids = self.row_set.values("object_id")
        return self.ModelClass.objects.filter(id__in=ids)

    def created(self):
        ids = self.row_set.filter(status=RowStatus.CREATED).values("object_id")
        return self.ModelClass.objects.filter(id__in=ids)

    def updated(self):
        ids = self.row_set.filter(status=RowStatus.UPDATED).values("object_id")
        return self.ModelClass.objects.filter(id__in=ids)

    def deleted(self):
        ids = self.row_set.filter(status=RowStatus.DELETED).values("object_id")
        return self.ModelClass.objects.filter(id__in=ids)

    def unknown(self):
        ids = self.row_set.filter(status=RowStatus.UNKNOWN).values("object_id")
        return self.ModelClass.objects.filter(id__in=ids)

    def delete_created(self):
        if self.status == self.Status.COMPLETED:
            for row in self.row_set.all():
                if row.status == RowStatus.CREATED:
                    row.target.delete()
                    row.status = RowStatus.DELETED
                    row.target = None
                    row.save()
            self.status = self.Status.DELETED
            self.save()


class ScribeRow(models.Model):
    store = models.ForeignKey(
        ScribeStore, on_delete=models.CASCADE, related_name="row_set"
    )
    object_index = models.IntegerField()
    data = models.JSONField()
    status = models.CharField(max_length=1, choices=RowStatus.choices, default="X")
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, blank=True, null=True
    )
    object_id = models.PositiveIntegerField(blank=True, null=True)
    target = GenericForeignKey("content_type", "object_id")

    def __str__(self):
        return "%s @%s -> index: %s" % (
            self.store.source.slug,
            self.store.downloaded_at.strftime("%Y/%m/%d %H:%M"),
            self.object_index,
        )

    @admin.display(ordering="object_id", description="target")
    def get_target_link(self):
        if self.object_id is None:
            return None
        admin_url = reverse(
            "admin:%s_%s_change"
            % (self.content_type.app_label, self.content_type.model),
            args=[self.object_id],
        )
        return mark_safe('<a href="%s">%s</a>' % (admin_url, self.target))

    @admin.display(description="data")
    def get_data_formatted(self):
        return mark_safe("<pre>%s</pre>" % json.dumps(json.loads(self.data), indent=4))
