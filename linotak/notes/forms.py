"""Forms for use in the notes app."""

from django.forms import Form, CharField, ModelChoiceField, HiddenInput, Textarea

from .models import Person, Series, Note


class NoteForm(Form):
    """Form for creating or editing a note.

    Not using modelform because we munge the text field.
    """

    series = ModelChoiceField(
        queryset=Series.objects.all(),
        widget=HiddenInput,
    )
    text = CharField(
        required=True,
        widget=Textarea(attrs={'cols': 80, 'rows': 5}),
    )
    author = ModelChoiceField(
        required=True,
        queryset=Person.objects.none(),
    )

    def __init__(self, login, initial=None, instance=None, **kwargs):
        # Want to constrain author choices to editors of series of note.
        # Must have series in the initial data or else.
        series = instance and instance.series or initial and initial.get('series')
        if not series:
            raise ValueError('must specify series or supply instance with series')

        if instance:
            self.instance = instance
            object_data = {
                'text': instance.text_with_links(),  # Pull URLs and tags back in to the text.
                'author': instance.author,
            }
        else:
            self.instance = Note(series=series)
            object_data = {
                'text': '',
                'author': None,
            }
        if initial:
            object_data.update(initial)
        object_data['series'] = series

        queryset = series.editors.filter(login=login)
        if not object_data.get('author'):
            object_data['author'] = queryset[0]

        super().__init__(initial=object_data, **kwargs)

        if series:
            self.fields['author'].queryset = queryset

    def save(self, **kwargs):
        """Ensure subject locators are copied to the form."""
        self.instance.author = self.cleaned_data['author']
        self.instance.text = self.cleaned_data['text']
        is_new = not self.instance.pk
        if is_new:
            self.instance.save()  # Needed before extract_subject to allow subjects to be added.
        if self.instance.extract_subject() or is_new:
            self.instance.save()
        return self.instance

