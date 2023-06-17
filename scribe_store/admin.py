from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils.safestring import mark_safe

from scribe_store.models import ScribeRow

from . import models


@admin.register(models.ScribeSource)
class ScribeSourceAdmin(admin.ModelAdmin):
    list_display = (
        "slug",
        "data_type",
        "url",
        "target",
    )
    list_filter = ("data_type", "target")


@admin.action(description="Delete data created by this file")
def delete_created(modeladmin, request, queryset):
    for datastore in queryset:
        datastore.delete_created()


@admin.register(models.ScribeStore)
class ScribeStoreAdmin(admin.ModelAdmin):
    list_display = (
        "slug",
        "source",
        "url",
        "file",
        "downloaded_at",
        "completed_at",
        "status",
    )
    list_filter = ("source",)
    actions = [delete_created]


@admin.register(models.ScribeRow)
class ScribeRowAdmin(admin.ModelAdmin):
    list_display = ("__str__", "object_index", "status", "get_target_link")
    readonly_fields = ["get_target_link", "get_data_formatted"]

    def get_fields(self, request, obj):
        fields = super().get_fields(request, obj)
        if fields[-2:] == ["get_target_link", "get_data_formatted"]:
            return fields[-2:] + fields[:-2]
        return fields


class ScribeAdminMixin:
    def get_scribe_row_admin_link(self, row):
        admin_url = reverse(
            "admin:%s_%s_change" % ("scribe_store", "scriberow"),
            args=[row.object_id],
        )
        return mark_safe('<a href="%s">%s</a>' % (admin_url, row))

    @admin.display(empty_value="")
    def scribe_row(self, obj):
        try:
            row = ScribeRow.objects.filter(
                content_type=ContentType.objects.get_for_model(obj.__class__),
                object_id=obj.id,
            ).all()
            return mark_safe(
                "<br>".join([self.get_scribe_row_admin_link(r) for r in row])
            )
        except ScribeRow.DoesNotExist:
            return None

    @admin.display(empty_value="")
    def scribe_data(self, obj):
        try:
            row = ScribeRow.objects.filter(
                content_type=ContentType.objects.get_for_model(obj.__class__),
                object_id=obj.id,
            ).all()
            return mark_safe("<br>".join([r.get_data_formatted() for r in row]))
        except ScribeRow.DoesNotExist:
            return None

    def get_list_display(self, request):
        return super().get_list_display(request) + ["scribe_row"]

    def get_readonly_fields(self, request, obj):
        return super().get_readonly_fields(request, obj) + ("scribe_row", "scribe_data")
