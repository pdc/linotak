"""Test for some views."""

import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.utils.timezone import now

from ...images.models import Image, Representation
from ..models import Locator, LocatorImage
from ..tag_filter import TagFilter
from ..views import Link, NoteDetailView, NoteListView
from .factories import LocatorFactory, NoteFactory, PersonFactory, SeriesFactory


@override_settings(NOTES_DOMAIN="example.com", ALLOWED_HOSTS=[".example.com"])
class TestNoteListView(TestCase):
    def test_redirects_to_about_page_if_no_series(self):
        r = self.client.get("/", HTTP_HOST="example.com", follow=True)

        self.assertEqual(r.redirect_chain, [("/about/", 302)])

    def test_filters_by_series(self):
        series = SeriesFactory.create(name="bar")
        note = NoteFactory.create(series=series, published=now())
        other = SeriesFactory.create()
        NoteFactory.create(
            series=other, published=now()
        )  # Will be omitted because wrong series

        r = self.client.get("/", HTTP_HOST="bar.example.com")

        self.assertEqual(r.context["series"], series)
        self.assertEqual(list(r.context["object_list"]), [note])
        self.assertEqual(list(r.context["note_list"]), [note])

    def test_filters_by_series_with_tilde(self):
        series = SeriesFactory.create(name="bar")
        note = NoteFactory.create(series=series, published=now())
        other = SeriesFactory.create()
        NoteFactory.create(
            series=other, published=now()
        )  # Will be omitted because wrong series

        r = self.client.get("/~bar/", HTTP_HOST="example.com")

        self.assertEqual(r.context["series"], series)
        self.assertEqual(list(r.context["object_list"]), [note])
        self.assertEqual(list(r.context["note_list"]), [note])

    def test_excludes_unpublished_notes(self):
        series = SeriesFactory.create(name="bar")
        author = PersonFactory.create()
        series.note_set.create(text="note1", author=author)
        note2 = series.note_set.create(text="note2", author=author, published=now())
        self.client.logout()

        r = self.client.get("/", HTTP_HOST="bar.example.com")

        self.assertEqual(
            r.resolver_match.func.__name__, NoteListView.as_view().__name__
        )
        self.assertEqual(list(r.context["object_list"]), [note2])
        self.assertFalse(r.context["can_edit_as"])

    def test_includes_create_button_if_editor(self):
        author = PersonFactory.create()
        SeriesFactory.create(name="bar", editors=[author])
        self.given_logged_in_as(author)

        r = self.client.get("/", HTTP_HOST="bar.example.com")

        self.assertEqual(list(r.context["can_edit_as"]), [author])

    def test_includes_drafts_if_editor(self):
        author = PersonFactory.create()
        series = SeriesFactory.create(name="bar", editors=[author])
        note = NoteFactory.create(author=author, series=series, text="text of note")
        NoteFactory.create(
            author=author, series=series, text="published", published=now()
        )
        self.given_logged_in_as(author)

        r = self.client.get("/drafts/", HTTP_HOST="bar.example.com")

        self.assertEqual(list(r.context["object_list"]), [note])

    def test_redirects_from_drafts_to_login_if_not_logged_in(self):
        SeriesFactory.create(name="baz")

        r = self.client.get("/drafts/", HTTP_HOST="baz.example.com", follow=True)

        self.assertEqual(r.redirect_chain, [("/accounts/login/?next=/drafts/", 302)])

    def test_returns_forbidden_if_not_editor(self):
        # Unlike not being loggged in, this should not happen in normal circumstances.
        SeriesFactory.create(name="baz")
        not_editor = PersonFactory()
        self.given_logged_in_as(not_editor)

        logging.disable(logging.CRITICAL)
        r = self.client.get("/drafts/", HTTP_HOST="baz.example.com")
        logging.disable(logging.NOTSET)

        self.assertEqual(r.status_code, 403)

    def test_fitered_by_tag_if_specified(self):
        series = SeriesFactory.create(name="alpha")
        note1 = NoteFactory.create(
            series=series, tags=["foo", "bar", "baz"], published=now()
        )
        NoteFactory.create(series=series, tags=["bar", "baz"], published=now())
        note3 = NoteFactory.create(
            series=series, tags=["qux", "foo", "bar"], published=now()
        )

        r = self.client.get("/tagged/foo+bar/", HTTP_HOST="alpha.example.com")

        self.assertEqual(list(r.context["object_list"]), [note3, note1])
        self.assertEqual(r.context["tag_filter"], TagFilter(["foo", "bar"]))
        self.assertIn(
            Link("alternate", "/tagged/bar+foo/atom/", "application/atom+xml"),
            r.context["links"](),
        )

    def test_includes_tags_in_atom_link(self):
        SeriesFactory.create(name="alpha")

        r = self.client.get("/tagged/foo+bar/", HTTP_HOST="alpha.example.com")

        self.assertIn(
            Link("alternate", "/tagged/bar+foo/atom/", "application/atom+xml"),
            r.context["links"](),
        )

    def test_omits_atom_link_from_drafts(self):
        author = PersonFactory.create()
        SeriesFactory.create(name="bar", editors=[author])
        self.given_logged_in_as(author)

        r = self.client.get("/drafts/", HTTP_HOST="bar.example.com")

        self.assertNotIn("alternate", {x.rel for x in r.context["links"]()})

    def given_logged_in_as(self, person):
        self.client.login(username=person.login.username, password="secret")


@override_settings(NOTES_DOMAIN="example.com", ALLOWED_HOSTS=[".example.com"])
class TestNoteFeedView(TestCase):
    """Tests for comformance to

    https://tools.ietf.org/html/rfc4287 – The Atom Syndication Format
    https://tools.ietf.org/html/rfc5005 -  Feed Paging and Archiving

    """

    maxDiff = 10_000

    def test_fitered_by_tag_if_specified(self):
        series = SeriesFactory.create(name="alpha", title="Series Title")
        author = PersonFactory.create(native_name="Alice de Winter")
        latest = datetime(2019, 2, 21, 22, 19, 45, 0, tzinfo=timezone.utc)
        NoteFactory.create(
            series=series,
            author=author,
            pk=13,
            tags=["foo", "bar", "baz"],
            text="Note 1 text",
            published=latest,
        )
        NoteFactory.create(
            series=series,
            author=author,
            pk=11,
            tags=["bar", "baz"],
            published=latest - timedelta(days=1),
        )
        NoteFactory.create(
            series=series,
            author=author,
            pk=9,
            tags=["qux", "foo", "bar"],
            text="Note 3 text",
            published=latest - timedelta(days=2),
        )

        r = self.client.get("/tagged/foo+bar/atom/", HTTP_HOST="alpha.example.com")

        self.assertEqual(
            r.content.decode("UTF-8"),
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="en-GB">\n'
            "    <id>https://alpha.example.com/tagged/bar+foo/</id>\n"
            "    <title>Series Title</title>\n"
            # TODO category
            '    <link href="https://alpha.example.com/tagged/bar+foo/atom/" rel="self"/>\n'
            '    <link href="https://alpha.example.com/tagged/bar+foo/"/>\n'
            "    <updated>2019-02-21T22:19:45Z</updated>\n"
            "    <entry>\n"
            "        <id>https://alpha.example.com/13</id>\n"
            "        <title>13</title>\n"
            "        <author>\n"
            "            <name>Alice de Winter</name>\n"
            "        </author>\n"
            "        <content>Note 1 text\n\n#bar #baz #foo</content>\n"
            "        <published>2019-02-21T22:19:45Z</published>\n"
            "        <updated>2019-02-21T22:19:45Z</updated>\n"
            '        <link href="https://alpha.example.com/tagged/bar+foo/13"/>\n'
            "    </entry>\n"
            "    <entry>\n"
            "        <id>https://alpha.example.com/9</id>\n"
            "        <title>9</title>\n"
            "        <author>\n"
            "            <name>Alice de Winter</name>\n"
            "        </author>\n"
            "        <content>Note 3 text\n\n#bar #foo #qux</content>\n"
            "        <published>2019-02-19T22:19:45Z</published>\n"
            "        <updated>2019-02-19T22:19:45Z</updated>\n"
            '        <link href="https://alpha.example.com/tagged/bar+foo/9"/>\n'
            "    </entry>\n"
            "</feed>",
        )


@override_settings(NOTES_DOMAIN="example.com", ALLOWED_HOSTS=[".example.com"])
@patch.object(NoteListView, "paginate_by", 30)
class TestNoteListPagination(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.series = SeriesFactory.create(name="bar")
        cls.notes = [
            NoteFactory.create(series=cls.series, published=(now() - timedelta(days=i)))
            for i in range(64)
        ]

    def test_adds_next_link_at_start(self):
        r = self.client.get("/", HTTP_HOST="bar.example.com")

        self.assertEqual(list(r.context["note_list"]), self.notes[:30])
        frags = {x.strip() for x in r["Link"].split(",")}
        self.assertIn("</page2/>; rel=next", frags)
        self.assertIn(Link("next", "/page2/"), r.context["links"]())

    def test_adds_both_links_in_middle(self):
        r = self.client.get("/page2/", HTTP_HOST="bar.example.com")

        self.assertEqual(list(r.context["note_list"]), self.notes[30:60])
        frags = {x.strip() for x in r["Link"].split(",")}
        self.assertIn("</>; rel=prev", frags)
        self.assertIn("</page3/>; rel=next", frags)

    def test_omits_page_numebr_from_feed_link(self):
        r = self.client.get("/page2/", HTTP_HOST="bar.example.com")

        self.assertIn(
            Link("alternate", "/atom/", "application/atom+xml"), r.context["links"]()
        )


@override_settings(NOTES_DOMAIN="example.com", ALLOWED_HOSTS=[".example.com"])
class TestNoteUpdateView(TestCase):
    def setUp(self):
        self.client = Client()
        self.author = PersonFactory.create()
        self.series = SeriesFactory.create(name="eg", editors=[self.author])
        self.client.login(username=self.author.login.username, password="secret")

    def test_passes_series_and_author(self):
        Locator.objects.create(url="http://example.com/1")
        Locator.objects.create(url="http://example.com/2")

        r = self.client.get("/new", HTTP_HOST="eg.example.com")

        self.assertEqual(r.context["form"].initial["series"], self.series)
        self.assertEqual(r.context["form"].initial["author"], self.author)

    def test_creates_note_on_post(self):
        r = self.client.post(
            "/new",
            {
                "series": str(self.series.pk),  # From intitial
                "author": str(self.author.pk),
                "text": "NOTE TEXT https://example.com/NOTE-URL",
            },
            HTTP_HOST="eg.example.com",
            follow=True,
        )

        self.assertFalse("form" in r.context and r.context["form"].errors)

        # Redirected to new note.
        self.assertEqual(
            r.resolver_match.func.__name__, NoteDetailView.as_view().__name__
        )
        self.assertTrue(r.context.get("note"))
        note = r.context["note"]
        self.assertEqual(note.text, "NOTE TEXT")
        self.assertTrue(note.subjects.all())
        self.assertEqual(note.subjects.all()[0].url, "https://example.com/NOTE-URL")


@override_settings(NOTES_DOMAIN="example.com", ALLOWED_HOSTS=[".example.com"])
class TestAuthorProfileView(TestCase):
    def test_fetches_person_and_series(self):
        author = PersonFactory(slug="some-slug")

        r = self.client.get("/some-slug", HTTP_HOST="example.com")

        self.assertEqual(r.context["object"], author)
        self.assertEqual(r.context["person"], author)
        self.assertFalse(r.context["series"])

    def test_links_to_feed(self):
        author = PersonFactory(slug="some-slug")
        series = SeriesFactory(name="nnn", editors=[author])

        r = self.client.get("/some-slug", HTTP_HOST="nnn.example.com")

        self.assertEqual(r.context["series"], series)
        self.assertIn(
            Link(href="https://nnn.example.com/", rel="feed"), r.context["links"]()
        )


@override_settings(NOTES_DOMAIN="example.com", ALLOWED_HOSTS=[".example.com"])
class TestLocatorImagesView(TestCase):
    def test_supplies_note_and_locator(self):
        locator = LocatorFactory()
        note = NoteFactory(series__name="smoo", subjects=[locator])
        image = Image.objects.create(data_url="https://example.com/a.png")
        locator_image = LocatorImage.objects.create(
            locator=locator, image=image, prominence=3
        )

        r = self.client.get(
            f"/{note.pk}/subjects/{locator.pk}/images/", HTTP_HOST="smoo.example.com"
        )

        self.assertEqual(r.context["note"], note)
        self.assertEqual(r.context["locator"], locator)
        self.assertTrue(r.context["formset"])
        self.assertEqual(r.context["formset"][0].instance, locator_image)

    def test_updates_locator_images(self):
        locator = LocatorFactory()
        note = NoteFactory(series__name="smoo", subjects=[locator])
        images = [
            Image.objects.create(data_url=f"https://example.com/{i}.png")
            for i in range(3)
        ]
        locator_images = [
            LocatorImage.objects.create(locator=locator, image=image)
            for image in images
        ]

        data = {
            "form-TOTAL_FORMS": "3",
            "form-INITIAL_FORMS": "3",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-prominence": "0",
            "form-0-id": str(locator_images[0].pk),
            "form-1-prominence": "1",
            "form-1-id": str(locator_images[1].pk),
            "form-2-prominence": "0",
            "form-2-id": str(locator_images[2].pk),
        }
        r = self.client.post(
            f"/{note.pk}/subjects/{locator.pk}/images/",
            data=data,
            HTTP_HOST="smoo.example.com",
            follow=False,
        )

        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, f"/drafts/{note.pk}")
        for locator_image in locator_images:
            locator_image.refresh_from_db()
        self.assertEqual([x.prominence for x in locator_images], [0, 1, 0])


@override_settings(NOTES_DOMAIN="example.com", ALLOWED_HOSTS=[".example.com"])
class TestLocatorImageUpdateView(TestCase):
    def test_supplies_image(self):
        locator = LocatorFactory()
        note = NoteFactory(series__name="smoo", subjects=[locator])
        image = Image.objects.create(data_url="https://example.com/a.png")
        LocatorImage.objects.create(locator=locator, image=image, prominence=3)

        r = self.client.get(
            f"/{note.pk}/subjects/{locator.pk}/images/{image.pk}",
            HTTP_HOST="smoo.example.com",
        )

        self.assertEqual(r.context["note"], note)
        self.assertEqual(r.context["locator"], locator)
        self.assertEqual(r.context["object"], image)
        self.assertEqual(r.context["form"].instance, image)

    def test_deletes_cropped_representations(self):
        locator = LocatorFactory()
        note = NoteFactory(series__name="smoo", subjects=[locator])
        image = Image.objects.create(data_url="https://example.com/a.png")
        cropped = Representation.objects.create(
            image=image, width=13, height=13, is_cropped=True
        )
        not_cropped = Representation.objects.create(
            image=image, width=13, height=13, is_cropped=False
        )
        LocatorImage.objects.create(locator=locator, image=image, prominence=3)

        data = {
            "focus_x": "0.333",
            "focus_y": "0.667",
            "crop_left": "0.0",
            "crop_top": "0.0",
            "crop_width": "1.0",
            "crop_height": "1.0",
        }
        r = self.client.post(
            f"/{note.pk}/subjects/{locator.pk}/images/{image.pk}",
            data=data,
            HTTP_HOST="smoo.example.com",
            follow=False,
        )

        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, f"/drafts/{note.pk}/subjects/{locator.pk}/images/")
        image.refresh_from_db()
        self.assertEqual((image.focus_x, image.focus_y), (0.333, 0.667))
        self.assertFalse(Representation.objects.filter(pk=cropped.pk).exists())
        self.assertTrue(Representation.objects.filter(pk=not_cropped.pk).exists())


@override_settings(NOTES_DOMAIN="example.com", ALLOWED_HOSTS=[".example.com"])
class TestNotCreateFormView(TestCase):
    def test_supplies_image(self):
        author = PersonFactory.create()
        self.given_logged_in_as(author)
        SeriesFactory.create(name="smoo", editors=[author])

        r = self.client.get(
            "/new?u=https:%2F%2Fexample.net%2F1&t=Text+from+query+string",
            HTTP_HOST="smoo.example.com",
        )

        form = r.context["form"]
        self.assertEqual(
            form.initial["text"], "Text from query string\n\nhttps://example.net/1"
        )

    def given_logged_in_as(self, person):
        self.client.login(username=person.login.username, password="secret")
