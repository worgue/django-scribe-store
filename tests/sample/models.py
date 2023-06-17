from django.db import models

from scribe_store import RowStatus

class Question(models.Model):
    question_text = models.CharField(max_length=200)
    pub_date = models.DateTimeField("date published")

    def __str__(self) -> str:
        return "Question: %s" % self.question_text


class News(models.Model):
    slug = models.SlugField(unique=True)
    news_text = models.CharField(max_length=200)
    pub_date = models.DateTimeField("date published")


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


class NewsCManager(models.Manager):
    def scribe_dict(self, data):
        if self.filter(slug=data["slug"]).exists():
            news = self.get(slug=data["slug"])
            news.news_text = data["news_text"]
            news.save()
            return news, RowStatus.UPDATED
        return self.create(**data)


class NewsC(models.Model):
    slug = models.SlugField(unique=True)
    news_text = models.CharField(max_length=200)
    pub_date = models.DateTimeField("date published")

    objects = NewsCManager()


class ChoiceManager(models.Manager):
    def scribe_dict(self, data):
        print(data)


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    choice_text = models.CharField(max_length=200)
    votes = models.IntegerField(default=0)

    objects = ChoiceManager()
