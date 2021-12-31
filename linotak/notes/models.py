import re

from django.conf import settings
from django.db import models, transaction
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from ..images.models import Image
from ..images.size_spec import SizeSpec
from .tag_filter import canonicalize_tag_name, wordify, camel_from_words


MAX_LENGTH = 4000


class Person(models.Model):
    """A person referred to as the author of some resource.

    *May* be associated with a login (for notes on this sytem),
    or may be a person whose profiles are all elsewhere.
    """

    login = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        models.SET_NULL,
        verbose_name=_("login"),
        null=True,
        blank=True,
        help_text=_(
            "If supplied, indicates this person  has an account on this system."
        ),
    )
    image = models.ForeignKey(
        Image,
        models.SET_NULL,
        verbose_name=_("image"),
        null=True,
        blank=True,
        help_text="Depicts this user.",
    )
    native_name = models.CharField(
        _("native name"),
        max_length=250,
        help_text=_("How this user’s name is presented."),
    )
    slug = models.SlugField(
        _("slug"),
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        help_text=_("Used in the URL for profile page for this person."),
    )
    description = models.TextField(
        _("description"),
        blank=True,
    )

    class Meta:
        verbose_name = _("person")
        verbose_name_plural = _("persons")

    def __str__(self):
        return self.native_name

    def get_absolute_url(self):
        """Return path to this person’s profile page."""
        return reverse("notes:person", kwargs={"slug": self.slug})

    def open_graph(self):
        """Dictionary of OpenGraph properties (as used by Facebook and sometimes Twitter)."""
        props = {
            "og:title": self.native_name,
            "og:type": "profile",
            "og:url": make_absolute_url(self.get_absolute_url()),
        }
        if self.image:
            representation = self.image.find_representation(
                SizeSpec(1080, 1080, min_ratio=(2, 3), max_ratio=(3, 2))
            )
            props.update(
                {
                    "og:image": representation.content.url,
                    "og:image:width": representation.width,
                    "og:image:height": representation.height,
                }
            )
        return props


class Profile(models.Model):
    """An online resource describing a person."""

    person = models.ForeignKey(
        Person,
        models.CASCADE,
        verbose_name=_("person"),
        related_name="profiles",
        related_query_name="profile",
    )

    url = models.URLField(
        _("URL"),
        max_length=MAX_LENGTH,
    )
    label = models.CharField(
        _("label"),
        max_length=MAX_LENGTH,
        help_text=_(
            "How to display the username or equivalent for this person on this site. E.g., @damiancugley if on twitter."
        ),
    )

    class Meta:
        verbose_name = _("profile")
        verbose_name_plural = _("profiles")

    def __str__(self):
        return self.label


class Locator(models.Model):
    """Information about a resource outside of our server, such as a site that is cited in a post."""

    author = models.ForeignKey(
        Person,
        models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("author"),
    )
    images = models.ManyToManyField(
        Image,
        through="LocatorImage",
        verbose_name="images",
        related_name="occurences",
        related_query_name="occurrence",
    )
    via = models.ForeignKey(
        "self",
        models.SET_NULL,
        related_name="destinatons",
        related_query_name="destination",
        null=True,
        blank=True,
        verbose_name="via",
        help_text="Link to another locator that referenced this one",
    )

    url = models.URLField(
        _("url"),
        max_length=MAX_LENGTH,
        unique=True,
    )
    title = models.CharField(
        _("title"),
        max_length=MAX_LENGTH,
        blank=True,
    )
    text = models.TextField(
        _("text"),
        blank=True,
        help_text=_("Description, summary, or content of the linked-to resource"),
    )
    sensitive = models.BooleanField(
        default=False,
        help_text=_(
            "Main image is ‘sensitive’ and should be hidden by default on Mastodon."
        ),
    )
    published = models.DateTimeField(
        _("published"),
        null=True,
        blank=True,
    )  # As claimed by the resource.
    scanned = models.DateTimeField(
        _("scanned"),
        null=True,
        blank=True,
    )

    created = models.DateTimeField(_("created"), default=timezone.now)
    modified = models.DateTimeField(_("modified"), auto_now=True)

    class Meta:
        verbose_name = _("locator")
        verbose_name_plural = _("locators")

    def __str__(self):
        return self.url

    def queue_fetch(self):
        """Arrange to have this locator’s page fetched and scanned."""
        from . import tasks

        t = self.scanned.timestamp() if self.scanned else None
        transaction.on_commit(
            lambda: tasks.fetch_locator_page.delay(self.pk, if_not_scanned_since=t)
        )

    def main_image(self):
        """Return the image with the highest prominence or largest source dimensions."""
        for image in self.images.filter(Q(width__isnull=True) | Q(height__isnull=True)):
            image.wants_size()
        candidates = list(
            self.images.filter(width__isnull=False, height__isnull=False).order_by(
                "-locatorimage__prominence", (F("width") * F("height")).desc()
            )[:1]
        )
        return candidates[0] if candidates else None

    def via_chain(self):
        """Return list of locators this locator was discovered via.

        First member of list (if any) is a page that links to this one.
        Second member of list (if any) is page that links to the first.
        Etc.
        """
        return list(self.via_iter())

    def via_iter(self):
        """Yield locators this locator was discovered via.

        First member of list (if any) is a page that links to this one.
        Second member of list (if any) is page that links to the first.
        Etc.
        """
        locator = self
        while locator.via:
            yield locator.via
            locator = locator.via


class LocatorImage(models.Model):
    """Relationship between locator and an image it references."""

    locator = models.ForeignKey(Locator, models.CASCADE, verbose_name=_("locator"))
    image = models.ForeignKey(Image, models.CASCADE, verbose_name=_("image"))
    prominence = models.PositiveSmallIntegerField(_("prominence"), default=0)

    class Meta:
        verbose_name = "locator image"
        verbose_name_plural = "locator images"
        ordering = ["-prominence"]
        unique_together = [["locator", "image"]]

    def __str__(self):
        return "%s->%s" % (self.locator, self.image)


class Series(models.Model):
    """A series of notes usually by one editor. Each series gets its own subdomain."""

    # Sizes of site (fav)icon recommended for Windows and for Android devices.
    ICON_SIZES = 16, 32, 48, 64, 192
    APPLE_TOUCH_ICON_SIZES = 120, 180, 152, 167

    editors = models.ManyToManyField(  # Links to persons (who have logins) who can create & update notes
        Person,
        verbose_name=_("editors"),
    )
    icon = models.ForeignKey(
        Image,
        models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("icon"),
        help_text=_("Optional favicon. Can use transparency. GIF or PNG."),
    )
    apple_touch_icon = models.ForeignKey(
        Image,
        models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Apple touch icon"),
        related_name="apple_touch_series_set",
        related_query_name="apple_touch_series",
        help_text=_("Optional apple-touch-icon. Not transparent."),
    )
    name = models.SlugField(
        _("name"),
        max_length=63,
        help_text=_("Uniquely identifies this series. Used in subdomain."),
    )
    title = models.CharField(
        _("title"),
        max_length=MAX_LENGTH,
    )
    desc = models.TextField(
        _("description"),
        blank=True,
        help_text=_("Optional description."),
    )
    created = models.DateTimeField(_("created"), default=timezone.now)
    modified = models.DateTimeField(_("modified"), auto_now=True)

    class Meta:
        ordering = ["title"]
        verbose_name = _("series")
        # Translator: plural
        verbose_name_plural = _("series")

    def __str__(self):
        return self.title or self.name

    def get_absolute_url(self, with_host=True):
        """Return path on site for this series.

        Includes schema & host by default because links from
        admin site or from other series’ pages will fail otherwise.
        """
        path = reverse("notes:list", kwargs={"drafts": False})
        return self.make_absolute_url(path) if with_host else path

    @property
    def domain(self):
        return f"{self.name}.{settings.NOTES_DOMAIN}"

    def make_absolute_url(self, path):
        """Given a path (starting with a slash) return a complate URL."""
        scheme = "http" if settings.NOTES_DOMAIN_INSECURE else "https"
        return f"{scheme}://{self.domain}{path}"

    def icon_representations(self):
        """Return sequence of image representations for use as favicons."""
        return icon_representations(self.icon, self.ICON_SIZES)

    def apple_touch_icon_representations(self):
        """Return sequence if image representations for use as favicons."""
        return icon_representations(self.apple_touch_icon, self.APPLE_TOUCH_ICON_SIZES)


def make_absolute_url(path):
    """Create absolute URL for path that does NOT want a series."""
    scheme = "http" if settings.NOTES_DOMAIN_INSECURE else "https"
    return f"{scheme}://{settings.NOTES_DOMAIN}{path}"


def icon_representations(image, sizes):
    """Return list of representations of this icon, or None."""
    if image:
        return [
            rep
            for rep in (image.find_square_representation(size) for size in sizes)
            if rep
        ]


class TagManager(models.Manager):
    """Manager for Tag instances."""

    def get_tag(self, proto_name):
        name = canonicalize_tag_name(proto_name)
        result, is_new = self.get_or_create(
            name=name, defaults={"label": wordify(proto_name)}
        )
        return result


class Tag(models.Model):
    """A token used to identify a subject in a note.

    Introduced in notes by adding them in camel-case pprefixed with #
    as in #blackAndWhite #landscape #tree

    The canonical name is all-lower-case, with words separated by hashes,
    and no prefix, as in `black-and-white`
    """

    name = models.SlugField(
        _("name"),
        max_length=MAX_LENGTH,
        blank=False,
        unique=True,
        help_text=_("Internal name of the tag, as lowercase words smooshed together."),
    )
    label = models.CharField(
        _("label"),
        max_length=MAX_LENGTH,
        blank=False,
        unique=True,
        help_text="Conventional capitalization of this tag, as words separated by spaces.",
    )

    created = models.DateTimeField(_("created"), default=timezone.now)
    modified = models.DateTimeField(_("modified"), auto_now=True)

    objects = TagManager()

    class Meta:
        ordering = ["label"]
        verbose_name = _("tag")
        verbose_name_plural = _("tags")

    def __str__(self):
        return self.label

    def as_camel_case(self):
        return camel_from_words(self.label)


class Note(models.Model):
    """Short text with optionalk links written by an editor, possibly published on the site.

    Editor enters text, hashtags, and subject URLs as one text.
    This is parsed in to text content, Tag and Subject instances.
    """

    series = models.ForeignKey(
        Series,
        models.CASCADE,
        verbose_name=_("series"),
    )
    author = models.ForeignKey(
        Person,
        models.CASCADE,
        verbose_name=_("author"),
    )
    tags = models.ManyToManyField(
        Tag,
        verbose_name=_("tags"),
        related_name="occurences",
        related_query_name="occurrence",
        blank=True,
    )
    subjects = models.ManyToManyField(
        Locator,
        through="NoteSubject",
        verbose_name=_("subjects"),
        related_name="occurences",
        related_query_name="occurrence",
        help_text=_("Web page or site that is described or cited in this note."),
    )
    text = models.TextField(
        _("text"),
        blank=True,
        help_text=_("Content of note. May be omitted if it has subject links."),
    )
    created = models.DateTimeField(_("created"), default=timezone.now)
    modified = models.DateTimeField(_("modified"), auto_now=True)
    published = models.DateTimeField(_("published"), null=True, blank=True)

    class Meta:
        verbose_name = _("note")
        verbose_name_plural = _("notes")
        ordering = ["-published", "-created"]

    def add_subject(self, url, via_url=None, **kwargs):
        """Add a subject locator."""
        if via_url:
            via, is_new = Locator.objects.get_or_create(url=via_url)
            kwargs["via"] = via
        locator, is_new = Locator.objects.get_or_create(url=url, defaults=kwargs)
        NoteSubject.objects.get_or_create(
            note=self,
            locator=locator,
            defaults={
                "sequence": 1 + len(self.subjects.all()),
            },
        )
        return locator

    def __str__(self):
        return self.short_title()

    def short_title(self):
        """Return a title for this note.

        Since notes do not have a separate title, we draw one from the
        first few words of the first line (paragraph) of the text.
        If the line must be shortened, then attempts to break at a space
        and make something 30-odd characters long.
        """
        if not self.text:
            if not self.id:
                return "(blank)"
            return "#%d" % self.id
        title = self.text.split("\n", 1)[0]
        if len(title) <= 30:
            return title
        pos = title.find(" ", 29)
        return "%s…" % title[:30] if pos < 0 else "%s …" % title[:pos]

    def text_with_links(self, with_citation=False, max_length=None, url_length=None):
        """Unparse note back in to text followed by tags and links.

        Arguments --
            with_citation -- if True, append a citation to the text (see <https://indieweb.org/permashortcitation>)
            max_length -- if set, ensure effective character count is no more than this.
                If it would be too long, return as much text as possible followed by ellipsis and
                link to the note itself
            url_length -- if set, treat subject URLs as being this length no matter how long they actually are.


        If none of the above optional arguments are supplied, then this function
        should return something that if re-parsed will yield an equivalent note.
        """
        text = self.text.strip()
        hashtags = " ".join("#" + x.as_camel_case() for x in self.tags.all())
        if with_citation:
            # https://indieweb.org/permashortcitation
            text = f"{text} ({self.series.name}.{settings.NOTES_DOMAIN} {self.pk})"

        if (
            max_length
            and effective_char_count(
                text, self.tags.all(), self.subjects.all(), url_length=url_length
            )
            > max_length
        ):
            # Too long so return shortend text and link to note.
            url = self.get_absolute_url(with_host=True)
            hashtags_part = ("\n\n" + hashtags) if hashtags else ""
            fixed_length = 2 + (url_length or len(url)) + len(hashtags_part)
            available_length = max_length - fixed_length
            if len(self.text) <= available_length:
                return f"{self.text}\n\n{url}{hashtags_part}"
            pos = self.text.rfind(" ", max(available_length - 20, 0), available_length)
            if pos > 0:
                pos += 1  # Include the space before the ellipsis
            else:
                pos = available_length  # This will cut off in mid-word.
            return f"{self.text[:pos]}… {url}{hashtags_part}"
        parts = [
            text,
            hashtags,
            "\n".join(
                "\n via ".join(
                    [f"{x.url} (nsfw)" if x.sensitive else x.url]
                    + [xx.url for xx in x.via_chain()]
                )
                for x in self.subjects.all()
            ),
        ]
        return "\n\n".join(x for x in parts if x)

    def get_absolute_url(
        self, view=None, tag_filter=None, drafts=None, with_host=False, **kwargs
    ):
        """Return URL for this note.

        Arguments (all optional) --
            view -- 'edit' to return URL for editing this node; default 'detail'
            tag_filter -- TagFilter instance, or None
            with_host -- add scheme and domain parts
        """
        path = reverse(
            "notes:%s" % (view or "detail"),
            kwargs={
                "pk": self.id,
                "tags": tag_filter.unparse() if tag_filter else "",
                "drafts": drafts if drafts is not None else not self.published,
                **kwargs,
            },
        )
        if with_host:
            return self.series.make_absolute_url(path)
        return path

    subject_re = re.compile(
        r"""
        (
            (?:
                \s*
                (?: \b via \s+ )?  # Optional `via` prefix.
                https?://
                [\w.-]+(?: :\d+)?
                (?: /\S* )?
                (?: \s+ \(nsfw\) )?  # Optional `(nsfw)` suffix.
            |
                (?:\s+ | ^)
                \# \w+
            )+
        )
        \s* $
        """,
        re.VERBOSE,
    )

    def extract_subject(self):
        """Anlyse the text of the note for URLs of subject(s) of the note."""
        m = Note.subject_re.search(self.text)
        excess_urls = set(
            x.url for x in self.subjects.all()
        )  # Will be reduced to just locators NOT mentioned in text.
        excess_tags = set(
            x.name for x in self.tags.all()
        )  # Will be reducted to just tags NOT mentioned in text
        prev_locator = None
        prev_locator_sensitive = False
        next_uri_is_via = False
        if m:
            things, self.text = m.group(1).split(), self.text[: m.start(0)].rstrip()
            for thing in things:
                if thing.startswith("#"):
                    tag = Tag.objects.get_tag(thing[1:])
                    if tag not in self.tags.all():
                        self.tags.add(tag)
                    excess_tags.discard(tag.name)
                elif thing == "via":
                    next_uri_is_via = True
                elif thing == "(nsfw)":
                    prev_locator_sensitive = True
                else:
                    # This will be the next locator, so time to finish up the prev locator.
                    if (
                        prev_locator
                        and prev_locator.sensitive != prev_locator_sensitive
                    ):
                        prev_locator.sensitive = prev_locator_sensitive
                        prev_locator.save()
                    # Normalize URLs lacking path component.
                    url = thing
                    if "/" not in url[8:]:
                        url += "/"
                    if next_uri_is_via:
                        locator, _ = Locator.objects.get_or_create(url=url)
                        prev_locator.via = locator
                        prev_locator.save()
                        NoteSubject.objects.filter(note=self, locator=locator).delete()
                        prev_locator = locator
                        next_uri_is_via = False
                    else:
                        prev_locator = self.add_subject(url)
                    excess_urls.discard(url)
                    prev_locator_sensitive = False
            # Finish off last locator
            if prev_locator and prev_locator.sensitive != prev_locator_sensitive:
                prev_locator.sensitive = prev_locator_sensitive
                prev_locator.save()
            # Delete any instances that are no longer wanted
            if excess_urls:
                NoteSubject.objects.filter(
                    note=self, locator__url__in=excess_urls
                ).delete()
            if excess_tags:
                self.tags.filter(name__in=excess_tags).delete()
            return things


def effective_char_count(text, tags, subjects, url_length=None):
    """Calculate the character count Twitter or Mastodon will give to this note.

    Arguments --
        text -- free-text portion of a note
        tags -- collection of Tag instances
        subjects -- collection of Location instances
        url_length -- if specified, assume all URLs are shortened to this length

    Mastodon also treats @-mentions specially, but since we do not use them
    we do not attempt to account for that in this function.
    """
    url_length = (
        2
        + sum(
            (url_length or len(locator.url))
            + sum(6 + (url_length or len(u)) for u in locator.via_chain())
            for locator in subjects
        )
        if subjects
        else 0
    )
    hashtag_length = 1 + sum(2 + len(x.name) for x in tags) if tags else 0

    return len(text) + url_length + hashtag_length


class NoteSubject(models.Model):
    """Relationship between a note and one of its subjects."""

    note = models.ForeignKey(Note, models.CASCADE, verbose_name=_("note"))
    locator = models.ForeignKey(Locator, models.CASCADE, verbose_name=_("locator"))
    sequence = models.PositiveSmallIntegerField(default=0, verbose_name=_("sequence"))

    class Meta:
        verbose_name = "note subject"
        verbose_name_plural = "note subjects"
        ordering = ["sequence"]
        unique_together = [
            ["note", "locator"],
        ]

    def __str__(self):
        return self.locator.url


def on_locator_post_save(sender, instance, created, **kwargs):
    """Signal handler for when a locator is saved."""
    if created and settings.NOTES_FETCH_LOCATORS:
        instance.queue_fetch()
