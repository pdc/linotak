"""Forms for use in the notes app."""

from django.forms import ModelForm

from .models import Note


class NoteForm(ModelForm):
    """Form for creating or editing a note."""

    class Meta:
        model = Note
        fields = ['text']
