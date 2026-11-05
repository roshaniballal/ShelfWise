from django.contrib import admin
from .models import Book


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "genre", "owner", "is_published")
    list_filter = ("genre", "is_published")
    search_fields = ("title", "author", "isbn")

    # ADMIN-LEVEL permission hooks. Each can override the default
    # model-permission check. Uncomment to experiment.

    # Example: only superusers may delete, even if user has delete_book.
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    # Example: non-superusers only see their own books in the admin list.
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(owner=request.user)

    # Example: object-level change check (only owner can edit).
    def has_change_permission(self, request, obj=None):
        has_perm = super().has_change_permission(request, obj)
        if obj is None:
            return has_perm
        return has_perm and (obj.owner == request.user or request.user.is_superuser)
