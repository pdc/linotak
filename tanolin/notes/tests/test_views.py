from django.test import Client, TestCase
from django.utils import timezone

from ..models import Locator
from ..tag_filter import TagFilter
from .factories import SeriesFactory, PersonFactory, NoteFactory


class TestNoteList(TestCase):
    def setUp(self):
        self.client = Client()

    def test_filters_by_series(self):
        series = SeriesFactory.create(name='bar')
        note = NoteFactory.create(series=series, published=timezone.now())
        other = SeriesFactory.create()
        NoteFactory.create(series=other, published=timezone.now())  # Will be omitted because wrong series

        r = self.client.get('/bar/')

        self.assertEqual(r.context['series'], series)
        self.assertEqual(list(r.context['object_list']), [note])
        self.assertEqual(list(r.context['note_list']), [note])

    def test_doesnt_filter_by_series_if_star(self):
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

        r = self.client.get('/bar/')

        self.assertEqual(list(r.context['object_list']), [note2])
        self.assertFalse(r.context['can_edit_as'])

    def test_includes_create_button_if_editor(self):
        author = PersonFactory.create()
        SeriesFactory.create(name='bar', editors=[author])
        self.given_logged_in_as(author)

        r = self.client.get('/bar/')

        self.assertEqual(list(r.context['can_edit_as']), [author])

    def test_includes_drafts_if_editor(self):
        author = PersonFactory.create()
        series = SeriesFactory.create(name='bar', editors=[author])
        note = NoteFactory.create(author=author, series=series, text='text of note')
        NoteFactory.create(author=author, series=series, text='published', published=timezone.now())
        self.given_logged_in_as(author)

        r = self.client.get('/bar/drafts/')

        self.assertEqual(list(r.context['object_list']), [note])

    def test_fitered_by_tag_if_specified(self):
        series = SeriesFactory.create(name='alpha')
        note1 = NoteFactory.create(series=series, tags=['foo', 'bar', 'baz'], published=timezone.now())
        note2 = NoteFactory.create(series=series, tags=['bar', 'baz'], published=timezone.now())
        note3 = NoteFactory.create(series=series, tags=['qux', 'foo', 'bar'], published=timezone.now())

        r = self.client.get('/alpha/tagged/foo+bar/')

        self.assertEqual(list(r.context['object_list']), [note3, note1])
        self.assertEqual(r.context['tag_filter'], TagFilter(['foo', 'bar']))

    def given_logged_in_as(self, person):
        self.client.login(username=person.login.username, password='secret')


class TestNoteUpdateView(TestCase):
    def setUp(self):
        self.client = Client()
        self.author = PersonFactory.create()
        self.series = SeriesFactory.create(name='bar', editors=[self.author])
        self.client.login(username=self.author.login.username, password='secret')

    def test_passes_series_and_author(self):
        Locator.objects.create(url='http://example.com/1')
        Locator.objects.create(url='http://example.com/2')

        r = self.client.get('/bar/new')

        self.assertEqual(r.context['form'].initial['series'], self.series)
        self.assertEqual(r.context['form'].initial['author'], self.author)

    def test_creates_note_on_post(self):
        r = self.client.post('/bar/new', {
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
        }, follow=True)

        self.assertFalse('form' in r.context and r.context['form'].errors)

        # Redirected to new note.
        self.assertTrue(r.context.get('note'))
        note = r.context['note']
        self.assertEqual(note.text, 'NOTE TEXT')
        self.assertTrue(note.subjects.all())
        self.assertEqual(note.subjects.all()[0].url, 'https://example.com/NOTE-URL')
