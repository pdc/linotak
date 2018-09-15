"""Forms for use in the notes app."""

from django.forms import ModelForm, Textarea

from .models import Note


class NoteForm(ModelForm):
    """Form for creating or editing a note."""

    class Meta:
        model = Note
        fields = ['text']

        widgets = {
            'text': Textarea(attrs={'cols': 80, 'rows': 3})
        }
