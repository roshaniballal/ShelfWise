from django import forms
from .models import Book


class BookForm(forms.ModelForm):
    # Extra checkbox, NOT a model field. It is only honoured if the user
    # also has the custom `publish_book` permission (checked in the view).
    publish_now = forms.BooleanField(required=False, label="Publish immediately")

    class Meta:
        model = Book
        fields = ["title", "author", "description", "genre", "isbn", "page_count", "publication_year"]
        widgets = {"description": forms.Textarea(attrs={"rows": 5, "cols": 50})}


class BookEditForm(forms.ModelForm):
    """Edit form. Deliberately has NO owner / is_published fields:
    ownership is fixed, and publishing needs the separate publish_book permission."""

    class Meta:
        model = Book
        fields = ["title", "author", "description", "genre", "isbn", "page_count", "publication_year"]
        widgets = {"description": forms.Textarea(attrs={"rows": 5, "cols": 50})}
