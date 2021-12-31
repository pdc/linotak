from django.test import TestCase

from ..forms import NoteForm
from .factories import PersonFactory, SeriesFactory, NoteFactory, LocatorFactory


class TestNoteForm(TestCase):
    """Tests for note form including subjects formset."""

    def setUp(self):
        self.alice = PersonFactory.create(native_name="Alice")
        self.bob = PersonFactory.create(native_name="Bob", login=self.alice.login)
        self.chandra = PersonFactory.create(native_name="Chandra")
        self.series = SeriesFactory.create(editors=[self.alice, self.bob, self.chandra])

    def test_new_form_acquires_author_from_series(self):
        form = NoteForm(self.alice.login, initial={"series": self.series})

        self.assertFalse(form.initial["text"])
        self.assertEqual(form.initial["series"], self.series)
        self.assertIn(form.initial["author"], {self.alice, self.bob})
        self.assertEqual(
            set(form.fields["author"].queryset.all()), {self.alice, self.bob}
        )

    def test_acquires_initial_values_from_instance(self):
        note = NoteFactory.create(
            series=self.series,
            text="Foo",
            author=self.alice,
            subjects=[
                LocatorFactory.create(url="http://example.com/1"),
            ],
        )

        form = NoteForm(self.alice.login, instance=note)

        self.assertEqual(form.initial["text"], "Foo\n\nhttp://example.com/1")
        self.assertEqual(form.initial["series"], self.series)
        self.assertEqual(form.initial["author"], self.alice)

    def test_subject_locators_are_updated_from_post(self):
        post_data = {
            "text": "Text of note http://examnple.com/1",
            "series": str(self.series.pk),
            "author": str(self.alice.pk),
        }
        form = NoteForm(
            self.alice.login,
            initial={"series": self.series, "author": self.alice},
            data=post_data,
        )

        self.assertValid(form)
        result = form.save()

        self.assertTrue(result)
        self.assertEqual(result.text, "Text of note")
        self.assertEqual(result.author, self.alice)
        self.assertEqual(result.series, self.series)
        self.assertEqual(len(result.subjects.all()), 1)
        self.assertEqual(result.subjects.all()[0].url, "http://examnple.com/1")

    def assertValid(self, form):
        """Check this form is valid in a way that hopefully exposes helpful error messages."""
        self.assertFalse(form.errors)
        self.assertTrue(form.is_valid())
