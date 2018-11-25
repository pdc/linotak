from datetime import datetime

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from customuser.models import Login
from ..forms import NoteForm, LocatorForm, LocatorFormset
from .. import forms  # for mocking
from ..models import Series, Locator, Note, NoteSubject
from .factories import PersonFactory, SeriesFactory


THEN = datetime(2018, 9, 29, 18, 54, 32, tzinfo=timezone.utc)
NOW = datetime(2018, 9, 30, 11, 16, 32, tzinfo=timezone.utc)


class TestLocatorForm(TestCase):
    """Tests for the locator form, which has to cope with tricky uniqueness constraints."""
    def test_creates_locator_on_save(self):
        form = LocatorForm({
            'url': 'https://example.com/1',
            'title': 'Title',
            'text': 'Text.',
        })

        self.assertFalse(form.errors)
        result = form.save()

        self.assertEqual(result.url, 'https://example.com/1')
        self.assertEqual(result.title, 'Title')
        self.assertEqual(result.text, 'Text.')
        self.assertTrue(result.pk)
        self.assertEqual(Locator.objects.get(pk=result.pk), result)

    def test_updates_locator_if_same_url(self):
        old = Locator.objects.create(url='https://example.com/1', title='Old title', text='Old text', published=THEN)
        form = LocatorForm({
            'url': 'https://example.com/1',
            'title': 'New title',
            'text': 'New text.',
            'published': NOW,
        })

        self.assertFalse(form.errors)
        result = form.save()

        self.assertEqual(result.url, 'https://example.com/1')
        self.assertEqual(result.title, 'New title')
        self.assertEqual(result.text, 'New text.')
        self.assertEqual(result.published, NOW)
        self.assertEqual(result.pk, old.pk)
        self.assertEqual(Locator.objects.get(pk=result.pk), result)

    def test_leaves_fields_unchanged_if_blanbk_in_form(self):
        old = Locator.objects.create(url='https://example.com/1', title='Old title', text='Old text.', published=THEN)
        form = LocatorForm({
            'url': 'https://example.com/1',
        })

        self.assertFalse(form.errors)
        result = form.save()

        self.assertEqual(result.url, 'https://example.com/1')
        self.assertEqual(result.title, 'Old title')
        self.assertEqual(result.text, 'Old text.')
        self.assertEqual(result.published, THEN)

    def test_can_get_initial_from_instance(self):
        old = Locator.objects.create(url='https://example.com/1', title='Old title', text='Old text.', published=THEN)

        initial = LocatorForm.initial_from_instance(old)

        self.assertEqual(initial, {
            'url': 'https://example.com/1',
            'title': 'Old title',
            'text': 'Old text.',
            'published': THEN,
        })


class TestNoteForm(TestCase):
    """Tests for note form including subjects formset."""

    def setUp(self):
        self.alice = PersonFactory.create(native_name='Alice')
        self.series = SeriesFactory.create(editors=[self.alice])

    def test_new_form_has_empty_formset(self):
        form = NoteForm(self.alice.login, initial={'series': self.series, 'author': self.alice})

        self.assertTrue(form.subjects_formset)
        self.assertEqual(len(form.subjects_formset), 0)

    def test_edit_form_has_filled_formset(self):
        note = self.series.note_set.create(text='Foo', author=self.alice)
        NoteSubject.objects.create(note=note, locator=Locator.objects.create(url='http://example.com/1'))

        form = NoteForm(self.alice.login, instance=note)

        self.assertTrue(form.subjects_formset)
        self.assertEqual(len(form.subjects_formset), 1)
        self.assertEqual(form.subjects_formset[0].initial['url'], 'http://example.com/1')

    def test_subject_locators_are_updated_from_post(self):
        post_data = {
            'text': 'Text of note',
            'series': str(self.series.pk),
            'author': str(self.alice.pk),
            'subj-TOTAL_FORMS': '1',
            'subj-INITIAL_FORMS': '0',
            'subj-MIN_NUM_FORMS': '0',
            'subj-MAX_NUM_FORMS': '1000',
            'subj-0-url': 'http://examnple.com/1',
            'subj-0-title': 'Title of subject',
            'subj-0-text': 'Text of subject',
            'subj-0-published': '',
            'subj-0-ORDER': '',
            'subj-0-id': '',
        }
        form = NoteForm(self.alice.login, initial={'series': self.series, 'author': self.alice}, data=post_data)

        self.assertValid(form)
        result = form.save()

        self.assertTrue(result)
        self.assertEqual(result.text, 'Text of note')
        self.assertEqual(result.author, self.alice)
        self.assertEqual(result.series, self.series)
        self.assertEqual(len(result.subjects.all()), 1)
        self.assertEqual(result.subjects.all()[0].url, 'http://examnple.com/1')
        self.assertEqual(result.subjects.all()[0].title, 'Title of subject')
        self.assertEqual(result.subjects.all()[0].text, 'Text of subject')

    def test_adds_extra_links_at_the_end(self):
        post_data = {
            'text': 'Text of note',
            'series': str(self.series.pk),
            'author': str(self.alice.pk),
            'subj-TOTAL_FORMS': '4',
            'subj-INITIAL_FORMS': '2',
            'subj-MIN_NUM_FORMS': '0',
            'subj-MAX_NUM_FORMS': '1000',
            'subj-0-url': 'http://examnple.com/p',
            'subj-0-ORDER': '2',
            'subj-1-url': 'http://examnple.com/q',
            'subj-1-ORDER': '1',
            'subj-2-url': 'http://examnple.com/r',
            'subj-2-ORDER': '',  # This is what happens with the extra form at the end.
            'subj-3-url': 'http://examnple.com/s',
            'subj-3-ORDER': '',
        }
        form = NoteForm(self.alice.login, initial={'series': self.series, 'author': self.alice}, data=post_data)

        self.assertValid(form)
        result = form.save()

        self.assertTrue(result)
        self.assertEqual([x.url for x in result.subjects.all()], [
            'http://examnple.com/q',
            'http://examnple.com/p',
            'http://examnple.com/r',
            'http://examnple.com/s',
        ])

    def test_note_form_can_delete(self):
        post_data = {
            'text': 'Text of note',
            'series': str(self.series.pk),
            'author': str(self.alice.pk),
            'subj-TOTAL_FORMS': '2',
            'subj-INITIAL_FORMS': '1',
            'subj-MIN_NUM_FORMS': '0',
            'subj-MAX_NUM_FORMS': '1000',
            'subj-0-url': 'http://examnple.com/p',
            'subj-0-ORDER': '2',
            'subj-1-url': 'http://examnple.com/q',
            'subj-1-ORDER': '1',
            'subj-0-DELETE': True,
        }
        form = NoteForm(self.alice.login, initial={'series': self.series, 'author': self.alice}, data=post_data)

        self.assertValid(form)
        result = form.save()

        self.assertTrue(result)
        self.assertEqual(len(result.subjects.all()), 1)
        self.assertEqual(result.subjects.all()[0].url, 'http://examnple.com/q')


    def test_extracts_subjects_from_text_of_note(self):
        post_data = {
            'text': 'Text of note https://example.com/1',
            'series': str(self.series.pk),
            'author': str(self.alice.pk),
            'subj-TOTAL_FORMS': '0',
            'subj-INITIAL_FORMS': '0',
            'subj-MIN_NUM_FORMS': '0',
            'subj-MAX_NUM_FORMS': '1000',
        }
        form = NoteForm(self.alice.login, initial={'series': self.series, 'author': self.alice}, data=post_data)

        self.assertValid(form)
        result = form.save()

        self.assertTrue(result)
        self.assertEqual(result.text, 'Text of note')
        self.assertEqual(len(result.subjects.all()), 1)
        self.assertEqual(result.subjects.all()[0].url, 'https://example.com/1')
        self.assertEqual(Note.objects.get(pk=result.pk).text, 'Text of note')

    def assertValid(self, form):
        """Check this form is valid in a way that hopefully exposes helpful error messages."""
        for errors in form.subjects_formset.errors:
            self.assertFalse(errors)
        self.assertFalse(form.errors)
        self.assertTrue(form.is_valid())
