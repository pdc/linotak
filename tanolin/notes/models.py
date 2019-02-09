import re

from django.conf import settings
from django.db import models, transaction
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone

from ..images.models import Image
from .tag_filter import canonicalize_tag_name, wordify


MAX_LENGTH = 4000


class Person(models.Model):
    """A person referred to as the author of some resource.

    May be associated with a login (for notes on this sytem),
    or a person whose profiles are all elsewhere.
    """

    login = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        models.SET_NULL,
        null=True,
        blank=True,
    )
    native_name = models.CharField(
        max_length=250,
        help_text='How this user’s name is presented.'
    )

    def __str__(self):
        return self.native_name


class Profile(models.Model):
    """An online resource describing a person."""

    person = models.ForeignKey(
        Person,
        models.CASCADE,
        related_name='profiles',
        related_query_name='profile',
    )

    url = models.URLField(
        max_length=MAX_LENGTH,
    )
    label = models.CharField(
        max_length=MAX_LENGTH,
        help_text='How to display the username or equivalent for this person on this site. E.g., @damiancugley if on twitter.'
    )

    def __str__(self):
        return self.label


class Locator(models.Model):
    """Information about a resource outside of our server, such as a site that is cited in a post."""

    author = models.ForeignKey(
        Person,
        models.SET_NULL,
        null=True,
        blank=True,
    )
    images = models.ManyToManyField(
        Image,
    )

    url = models.URLField(
        max_length=MAX_LENGTH,
        unique=True,
    )
    title = models.CharField(
        max_length=MAX_LENGTH,
        blank=True,
    )
    text = models.TextField(
        blank=True,
        help_text='Description, summary, or content of the linked-to resource'
    )
    published = models.DateTimeField(
        null=True,
        blank=True,
    )  # As claimed by the resource.
    scanned = models.DateTimeField(
        null=True,
        blank=True,
    )

    created = models.DateTimeField(default=timezone.now)
    modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.url

    def queue_fetch(self):
        """Arrange to have this locator’s page fetched and scanned."""
        from . import tasks

        t = (self.scanned.timestamp() if self.scanned else None)
        transaction.on_commit(lambda: tasks.fetch_locator_page.delay(self.pk, if_not_scanned_since=t))

    def main_image(self):
        """Return the image with the largest source dimensions."""
        for image in self.images.filter(Q(width__isnull=True) | Q(height__isnull=True)):
            image.wants_size()
        candidates = list(self.images.filter(width__isnull=False, height__isnull=False).order_by((F('width') * F('height')).desc())[:1])
        return candidates[0] if candidates else None


class Series(models.Model):
    editors = models.ManyToManyField(  # Links to persons (who have logins) who can create & update notes
        Person,
    )
    name = models.SlugField(
        max_length=63,
        help_text='Used in URLs',
    )
    title = models.CharField(
        max_length=MAX_LENGTH,
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


class TagManager(models.Manager):
    """Manager for Tag instances."""

    def get_tag(self, proto_name):
        name = canonicalize_tag_name(proto_name)
        result, is_new = self.get_or_create(name=name, defaults={'label': wordify(proto_name)})
        return result


class Tag(models.Model):
    """A token used to identify a subject in a note.

    Introduced in notes by adding them in camel-case pprefixed with #
    as in #blackAndWhite #landscape #tree

    The canonical name is all-lower-case, with words separated by hashes,
    and no prefix, as in `black-and-white`
    """

    name = models.SlugField(
        max_length=MAX_LENGTH,
        blank=False,
        unique=True,
        help_text='Internal name of the tag, as lowercase words separated by dashes.',
    )
    label = models.CharField(
        max_length=MAX_LENGTH,
        blank=False,
        unique=True,
        help_text='Conventional capitalization of this tag, as words separated by spaces.',
    )

    created = models.DateTimeField(default=timezone.now)
    modified = models.DateTimeField(auto_now=True)

    objects = TagManager()

    class Meta:
        ordering = ['label']

    def __str__(self):
        return self.label


class Note(models.Model):
    series = models.ForeignKey(
        Series,
        models.CASCADE,
    )
    author = models.ForeignKey(
        Person,
        models.CASCADE,
    )
    tags = models.ManyToManyField(
        Tag,
        related_name='occurences',
        related_query_name='occurrence',
        blank=True,
    )
    subjects = models.ManyToManyField(
        Locator,
        through='NoteSubject',
        related_name='occurences',
        related_query_name='occurrence',
        help_text='Web page or sites that is described or cited in this note.'
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

    def add_subject(self, url, **kwargs):
        """Add a subject locator."""
        locator, is_new = Locator.objects.get_or_create(url=url, defaults=kwargs)
        NoteSubject.objects.get_or_create(note=self, locator=locator, defaults={
            'sequence': 1 + len(self.subjects.all()),
        })
        return locator

    def __str__(self):
        if not self.text:
            if not self.id:
                return '(blank)'
            return '#%d' % self.id
        if len(self.text) <= 30:
            return self.text
        return '%s…' % self.text[:30]

    def get_absolute_url(self):
        return reverse('notes:detail', kwargs={
            'series_name': self.series.name,
            'pk': self.id,
            'drafts': not self.published,
            # 'page': 1,
            # 'tags': '',
        })

    subject_re = re.compile(r"""
        (
            (?:
                \s*
                https?://
                [\w.-]+(?: :\d+)?
                (?: /\S* )?
            |
                (\s+ | ^)
                \# \w+
            )+
        )
        \s* $
        """, re.VERBOSE)

    def extract_subject(self):
        """Anlyse the text of the note for URLs of subject(s) of the note."""
        m = Note.subject_re.search(self.text)
        if m:
            things, self.text = m.group(1).split(), self.text[:m.start(0)]
            for url in things:
                if url.startswith('#'):
                    tag = Tag.objects.get_tag(url[1:])
                    if tag not in self.tags.all():
                        self.tags.add(tag)
                else:
                    if '/' not in url[8:]:
                        url += '/'
                    self.add_subject(url)
            return things


class NoteSubject(models.Model):
    """Relationship between a note and one of its subjects."""

    note = models.ForeignKey(Note, models.CASCADE)
    locator = models.ForeignKey(Locator, models.CASCADE)
    sequence = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sequence']
        unique_together = [
            ['note', 'locator'],
        ]

    def __str__(self):
        return self.locator.url
