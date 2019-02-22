
from datetime import datetime, timedelta
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from ..models import Locator
from ..tag_filter import TagFilter
from ..views import NoteListView, NoteDetailView
from .factories import SeriesFactory, PersonFactory, NoteFactory


@override_settings(NOTES_DOMAIN='example.com', ALLOWED_HOSTS=['.example.com'])
class TestNoteListView(TestCase):

    def test_filters_by_series(self):
        series = SeriesFactory.create(name='bar')
        note = NoteFactory.create(series=series, published=timezone.now())
        other = SeriesFactory.create()
        NoteFactory.create(series=other, published=timezone.now())  # Will be omitted because wrong series

        r = self.client.get('/', HTTP_HOST='bar.example.com')

        self.assertEqual(r.context['series'], series)
        self.assertEqual(list(r.context['object_list']), [note])
        self.assertEqual(list(r.context['note_list']), [note])

    def xtest_doesnt_filter_by_series_if_star(self):
        series1 = SeriesFactory.create()
        note1 = NoteFactory.create(series=series1, published=timezone.now())
        series2 = SeriesFactory.create()
        note2 = NoteFactory.create(series=series2, published=timezone.now())

        r = self.client.get('/*/')

        self.assertFalse(r.context.get('series'))
        self.assertEqual(set(r.context['object_list']), {note1, note2})

    def test_excludes_unpublished_notes(self):
        series = SeriesFactory.create(name='bar')
        author = PersonFactory.create()
        series.note_set.create(text='note1', author=author)
        note2 = series.note_set.create(text='note2', author=author, published=timezone.now())
        self.client.logout()

        r = self.client.get('/', HTTP_HOST='bar.example.com')

        self.assertEqual(r.resolver_match.func.__name__, NoteListView.as_view().__name__)
        self.assertEqual(list(r.context['object_list']), [note2])
        self.assertFalse(r.context['can_edit_as'])

    def test_includes_create_button_if_editor(self):
        author = PersonFactory.create()
        SeriesFactory.create(name='bar', editors=[author])
        self.given_logged_in_as(author)

        r = self.client.get('/', HTTP_HOST='bar.example.com')

        self.assertEqual(list(r.context['can_edit_as']), [author])

    def test_includes_drafts_if_editor(self):
        author = PersonFactory.create()
        series = SeriesFactory.create(name='bar', editors=[author])
        note = NoteFactory.create(author=author, series=series, text='text of note')
        NoteFactory.create(author=author, series=series, text='published', published=timezone.now())
        self.given_logged_in_as(author)

        r = self.client.get('/drafts/', HTTP_HOST='bar.example.com')

        self.assertEqual(list(r.context['object_list']), [note])

    def test_fitered_by_tag_if_specified(self):
        series = SeriesFactory.create(name='alpha')
        note1 = NoteFactory.create(series=series, tags=['foo', 'bar', 'baz'], published=timezone.now())
        note2 = NoteFactory.create(series=series, tags=['bar', 'baz'], published=timezone.now())
        note3 = NoteFactory.create(series=series, tags=['qux', 'foo', 'bar'], published=timezone.now())

        r = self.client.get('/tagged/foo+bar/', HTTP_HOST='alpha.example.com')

        self.assertEqual(list(r.context['object_list']), [note3, note1])
        self.assertEqual(r.context['tag_filter'], TagFilter(['foo', 'bar']))

    def given_logged_in_as(self, person):
        self.client.login(username=person.login.username, password='secret')


@override_settings(NOTES_DOMAIN='example.com', ALLOWED_HOSTS=['.example.com'])
class TestNoteFeedView(TestCase):
    """Tests for comformance to

    https://tools.ietf.org/html/rfc4287 – The Atom Syndication Format
    https://tools.ietf.org/html/rfc5005 -  Feed Paging and Archiving

    """
    maxDiff = 10_000

    def test_fitered_by_tag_if_specified(self):
        series = SeriesFactory.create(name='alpha', title="Series Title")
        author = PersonFactory.create(native_name='Alice de Winter')
        latest = datetime(2019, 2, 21, 22, 19, 45, 0, tzinfo=timezone.utc)
        note1 = NoteFactory.create(series=series, author=author, pk=13, tags=['foo', 'bar', 'baz'], text='Note 1 text', published=latest)
        note2 = NoteFactory.create(series=series, author=author, pk=11, tags=['bar', 'baz'], published=latest - timedelta(days=1))
        note3 = NoteFactory.create(series=series, author=author, pk=9, tags=['qux', 'foo', 'bar'], text='Note 3 text', published=latest - timedelta(days=2))

        r = self.client.get('/tagged/foo+bar/atom/', HTTP_HOST='alpha.example.com')

        self.assertEqual(
            r.content.decode('UTF-8'),
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="en-GB">\n'
            '    <id>https://alpha.example.com/tagged/bar+foo/</id>\n'
            '    <title>Series Title</title>\n'
            # TODO category
            '    <link href="https://alpha.example.com/tagged/bar+foo/atom/" rel="self"/>\n'
            '    <link href="https://alpha.example.com/tagged/bar+foo/"/>\n'
            '    <updated>2019-02-21T22:19:45Z</updated>\n'
            '    <entry>\n'
            '        <id>https://alpha.example.com/13</id>\n'
            '        <title>13</title>\n'
            '        <author>\n'
            '            <name>Alice de Winter</name>\n'
            '        </author>\n'
            '        <content>Note 1 text\n\n#bar #baz #foo</content>\n'
            '        <published>2019-02-21T22:19:45Z</published>\n'
            '        <updated>2019-02-21T22:19:45Z</updated>\n'
            '        <link href="https://alpha.example.com/tagged/bar+foo/13"/>\n'
            '    </entry>\n'
            '    <entry>\n'
            '        <id>https://alpha.example.com/9</id>\n'
            '        <title>9</title>\n'
            '        <author>\n'
            '            <name>Alice de Winter</name>\n'
            '        </author>\n'
            '        <content>Note 3 text\n\n#bar #foo #qux</content>\n'
            '        <published>2019-02-19T22:19:45Z</published>\n'
            '        <updated>2019-02-19T22:19:45Z</updated>\n'
            '        <link href="https://alpha.example.com/tagged/bar+foo/9"/>\n'
            '    </entry>\n'
            '</feed>')


@override_settings(NOTES_DOMAIN='example.com', ALLOWED_HOSTS=['.example.com'])
class TestNoteUpdateView(TestCase):
    def setUp(self):
        self.client = Client()
        self.author = PersonFactory.create()
        self.series = SeriesFactory.create(name='eg', editors=[self.author])
        self.client.login(username=self.author.login.username, password='secret')

    def test_passes_series_and_author(self):
        Locator.objects.create(url='http://example.com/1')
        Locator.objects.create(url='http://example.com/2')

        r = self.client.get('/new', HTTP_HOST='eg.example.com')

        self.assertEqual(r.context['form'].initial['series'], self.series)
        self.assertEqual(r.context['form'].initial['author'], self.author)

    def test_creates_note_on_post(self):
        r = self.client.post('/new', {
            'series': str(self.series.pk),  # From intitial
            'author': str(self.author.pk),
            'text': 'NOTE TEXT',
            'subj-TOTAL_FORMS': '1',
            'subj-INITIAL_FORMS': '0',
            'subj-MIN_NUM_FORMS': '0',
            'subj-MAX_NUM_FORMS': '1000',
            'subj-0-url': 'https://example.com/NOTE-URL',
            'subj-0-title': '',
            'subj-0-text': '',
            'subj-0-published': '',
            'subj-0-ORDER': '',
            'subj-0-id': '',
        }, HTTP_HOST='eg.example.com', follow=True)

        self.assertFalse('form' in r.context and r.context['form'].errors)

        # Redirected to new note.
        self.assertEqual(r.resolver_match.func.__name__, NoteDetailView.as_view().__name__)
        self.assertTrue(r.context.get('note'))
        note = r.context['note']
        self.assertEqual(note.text, 'NOTE TEXT')
        self.assertTrue(note.subjects.all())
        self.assertEqual(note.subjects.all()[0].url, 'https://example.com/NOTE-URL')
