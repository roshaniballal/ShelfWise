from django.conf import settings
from django.db import models


class Genre(models.TextChoices):
    TECH = "tech", "Technology"
    SCIENCE = "science", "Science"
    FICTION = "fiction", "Fiction"
    NONFICTION = "nonfiction", "Non-fiction"
    HISTORY = "history", "History"
    OTHER = "other", "Other"


class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    genre = models.CharField(max_length=20, choices=Genre.choices, default=Genre.OTHER)
    isbn = models.CharField("ISBN", max_length=13, blank=True)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    publication_year = models.PositiveSmallIntegerField(null=True, blank=True)
    is_published = models.BooleanField(default=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="books"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # DEFAULT permissions (add_book, change_book, delete_book, view_book)
        # are created automatically by Django on `migrate`.
        #
        # CUSTOM permissions: you define extra ones here.
        permissions = [
            ("publish_book", "Can publish a book"),
            ("export_book", "Can export books to CSV"),
        ]

    def __str__(self):
        return self.title
