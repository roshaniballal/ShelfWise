from django.contrib import messages
from django.contrib.auth.decorators import (
    login_required, permission_required, user_passes_test,
)
from django.contrib.auth.mixins import (
    LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin,
)
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from .forms import BookEditForm, BookForm
from .models import Book


def _redirect_back(request, default="home"):
    """Go back to the page the form was submitted from (safe `next` only)."""
    nxt = request.POST.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(nxt)
    return redirect(default)


# ---------------------------------------------------------------
# 0. NO PERMISSION: anyone (even anonymous) can access
# ---------------------------------------------------------------
def home(request):
    return render(request, "library/home.html", {"books": Book.objects.select_related("owner")})


# ---------------------------------------------------------------
# 1. AUTHENTICATION ONLY: just needs to be logged in
# ---------------------------------------------------------------
@login_required
def dashboard(request):
    return HttpResponse(f"Hello {request.user.username}, you are logged in.")


# ---------------------------------------------------------------
# 2. DEFAULT MODEL PERMISSION via decorator
#    raise_exception=True -> 403 instead of redirecting to login
# ---------------------------------------------------------------
@permission_required("library.view_book", raise_exception=True)
def book_list(request):
    return HttpResponse("Books: " + ", ".join(Book.objects.values_list("title", flat=True)))


# ---------------------------------------------------------------
# 2b. DETAIL PAGE: model permission + a rule about DRAFT books
#     - needs view_book (model-level)
#     - drafts are only visible to the owner, or users who can
#       change/publish books (object-level rule, written by hand)
# ---------------------------------------------------------------
@login_required
@permission_required("library.view_book", raise_exception=True)
def book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)
    u = request.user
    can_see_draft = (
        book.owner_id == u.id
        or u.has_perm("library.change_book")
        or u.has_perm("library.publish_book")
    )
    if not book.is_published and not can_see_draft:
        # (Some sites raise Http404 here instead, to hide that the book exists.)
        raise PermissionDenied("This book is still a draft. Only its owner, editors and publishers can see it.")
    return render(request, "library/book_detail.html", {"book": book})


# ---------------------------------------------------------------
# 3. CUSTOM MODEL PERMISSION via decorator
# ---------------------------------------------------------------
# NOTE: decorator order matters. permission_required is OUTERMOST so the
# permission is checked first (403), then require_POST (405 for GET).
@permission_required("library.publish_book", raise_exception=True)
@require_POST
def publish_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    book.is_published = True
    book.save()
    messages.success(request, f"'{book.title}' was published.")
    return _redirect_back(request)


@permission_required("library.publish_book", raise_exception=True)
@require_POST
def unpublish_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    book.is_published = False
    book.save()
    messages.info(request, f"'{book.title}' was moved back to draft.")
    return _redirect_back(request)


# ---------------------------------------------------------------
# 3b. CREATE a book: needs add_book. Publishing it immediately ALSO
#     needs publish_book -> two permissions combined in one screen.
# ---------------------------------------------------------------
@permission_required("library.add_book", raise_exception=True)
def add_book(request):
    can_publish = request.user.has_perm("library.publish_book")
    if request.method == "POST":
        form = BookForm(request.POST)
        if form.is_valid():
            book = form.save(commit=False)
            book.owner = request.user
            # Server-side check: ignore the checkbox if user lacks publish_book
            book.is_published = bool(form.cleaned_data["publish_now"] and can_publish)
            book.save()
            state = "published" if book.is_published else "saved as draft"
            messages.success(request, f"'{book.title}' was {state}.")
            return redirect("home")
    else:
        form = BookForm()
    return render(request, "library/add_book.html", {"form": form, "can_publish": can_publish})


# ---------------------------------------------------------------
# 4. MULTIPLE PERMISSIONS (user must have ALL of them)
# ---------------------------------------------------------------
@permission_required(["library.view_book", "library.export_book"], raise_exception=True)
def export_books(request):
    return HttpResponse("title,author\n" + "\n".join(
        f"{b.title},{b.author}" for b in Book.objects.all()), content_type="text/csv")


# ---------------------------------------------------------------
# 5. CUSTOM RULE: user_passes_test (any Python condition)
# ---------------------------------------------------------------
def is_staff_member(user):
    return user.is_staff

@user_passes_test(is_staff_member)
def staff_only(request):
    return HttpResponse("Welcome, staff member.")


# ---------------------------------------------------------------
# 6. CLASS-BASED VIEW: PermissionRequiredMixin
# ---------------------------------------------------------------
class BookDeleteView(PermissionRequiredMixin, View):
    permission_required = "library.delete_book"
    raise_exception = True

    def post(self, request, pk):
        book = get_object_or_404(Book, pk=pk)
        title = book.title
        book.delete()
        messages.warning(request, f"'{title}' was deleted.")
        return redirect("home")


# ---------------------------------------------------------------
# 7. CLASS-BASED VIEW: UserPassesTestMixin (custom rule)
# ---------------------------------------------------------------
class SuperuserOnlyView(LoginRequiredMixin, UserPassesTestMixin, View):
    raise_exception = True

    def test_func(self):
        return self.request.user.is_superuser

    def get(self, request):
        return HttpResponse("Superuser area.")


# ---------------------------------------------------------------
# 8. OBJECT-LEVEL PERMISSION (done manually)
#    Django's built-in permissions are model-wide: "can edit ANY book".
#    "Can edit THIS book" needs your own check (or django-guardian).
# ---------------------------------------------------------------
@login_required
def edit_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    # Rule: the OWNER may edit their own book, and anyone with the
    # model-wide `change_book` permission may edit ANY book.
    if book.owner_id != request.user.id and not request.user.has_perm("library.change_book"):
        raise PermissionDenied("Only the owner of this book, or users with the 'change book' permission, can edit it.")

    if request.method == "POST":
        form = BookEditForm(request.POST, instance=book)
        if form.is_valid():
            form.save()
            messages.success(request, f"'{book.title}' was updated.")
            if request.user.has_perm("library.view_book"):
                return redirect("book_detail", pk=book.pk)
            return redirect("home")
    else:
        form = BookEditForm(instance=book)
    return render(request, "library/edit_book.html", {"form": form, "book": book})


# ---------------------------------------------------------------
# 9. CHECKING PERMISSIONS INSIDE CODE / TEMPLATES
# ---------------------------------------------------------------
@login_required
def my_permissions(request):
    u = request.user
    context = {
        "is_superuser": u.is_superuser,
        "is_staff": u.is_staff,
        "is_active": u.is_active,
        "all_perms": sorted(u.get_all_permissions()),      # user + group perms
        "user_perms": sorted(u.get_user_permissions()),    # directly assigned only
        "group_perms": sorted(u.get_group_permissions()),  # via groups only
        "groups": list(u.groups.values_list("name", flat=True)),
    }
    return render(request, "library/my_permissions.html", context)
