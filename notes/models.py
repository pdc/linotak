from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Series(models.Model):
    editors = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
    )
    name = models.SlugField(
        max_length=63,
        help_text='Used in URLs',
    )
    title = models.CharField(
        max_length=250,
    )
    desc = models.TextField(
        'description',
        blank=True,
        help_text="Optional description.",
    )
    created = models.DateTimeField(default=timezone.now)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['title']
        verbose_name_plural = 'series'

    def __str__(self):
        return self.title or self.name

    def get_absolute_url(self):
        return reverse('notes:list', kwargs={'series_name': self.name})


class Note(models.Model):
    series = models.ForeignKey(
        Series,
        on_delete=models.CASCADE,
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    text = models.TextField(
        blank=True,
        help_text="Content of note. May be omitted if it has subject links.",
    )
    created = models.DateTimeField(default=timezone.now)
    modified = models.DateTimeField(auto_now=True)
    published = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-published', '-created']

    def __str__(self):
        if not self.text:
            return '#%d' % self.id
        if len(self.text) <= 30:
            return self.text
        return '%s…' % self.text[:30]

    def get_absolute_url(self):
        return reverse('notes:detail', kwargs={'series_name': self.series.name, 'pk': self.id})

