from django.contrib import admin

from scribe_store.admin import ScribeAdminMixin

from .models import News, Question


@admin.register(Question)
class QuestionAdmin(ScribeAdminMixin, admin.ModelAdmin):
    list_display = ["question_text", "pub_date"]


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ["slug", "news_text", "pub_date"]
