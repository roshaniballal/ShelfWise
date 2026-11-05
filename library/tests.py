"""
Run:  python manage.py test -v 2
Each test is a tiny experiment showing ONE permission concept.
"""
from django.contrib.auth.models import Group, Permission, User
from django.test import TestCase

from .models import Book


class PermissionLab(TestCase):
    @classmethod
    def setUpTestData(cls):
        def p(code):
            return Permission.objects.get(codename=code, content_type__app_label="library")

        cls.owner = User.objects.create_user("owner", password="x")
        cls.book = Book.objects.create(title="T", author="A", owner=cls.owner)

        cls.nobody = User.objects.create_user("nobody", password="x")
        cls.viewer = User.objects.create_user("viewer", password="x")
        cls.viewer.user_permissions.add(p("view_book"))
        cls.publisher = User.objects.create_user("publisher", password="x")
        cls.publisher.user_permissions.add(p("publish_book"))
        cls.superuser = User.objects.create_superuser("root", password="x")
        cls.staff = User.objects.create_user("staff", password="x", is_staff=True)

        g = Group.objects.create(name="G")
        g.permissions.add(p("add_book"))
        cls.grouped = User.objects.create_user("grouped", password="x")
        cls.grouped.groups.add(g)

    def get(self, user, url):
        if user:
            self.client.force_login(user)
        return self.client.get(url)

    # 1. default permissions exist
    def test_default_permissions_auto_created(self):
        codes = set(Permission.objects.filter(content_type__app_label="library")
                    .values_list("codename", flat=True))
        self.assertTrue({"add_book", "change_book", "delete_book", "view_book"} <= codes)

    # 2. custom permissions exist
    def test_custom_permissions_created(self):
        self.assertTrue(Permission.objects.filter(codename="publish_book").exists())

    # 3. login_required: anonymous -> redirect to login
    def test_anonymous_redirected(self):
        r = self.get(None, "/dashboard/")
        self.assertEqual(r.status_code, 302)

    # 4. permission_required: logged in but lacking perm -> 403
    def test_missing_permission_is_403(self):
        self.assertEqual(self.get(self.nobody, "/books/").status_code, 403)

    def test_having_permission_is_200(self):
        self.assertEqual(self.get(self.viewer, "/books/").status_code, 200)

    # 5. permission via GROUP
    def test_group_permission(self):
        self.assertTrue(self.grouped.has_perm("library.add_book"))
        self.assertIn("library.add_book", self.grouped.get_group_permissions())
        self.assertNotIn("library.add_book", self.grouped.get_user_permissions())

    # 6. custom permission gates a view (publish is POST-only)
    def test_custom_permission_view(self):
        url = f"/books/{self.book.pk}/publish/"
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.post(url).status_code, 403)   # no publish_book
        self.client.force_login(self.publisher)
        self.assertEqual(self.client.get(url).status_code, 405)    # GET not allowed
        self.assertEqual(self.client.post(url).status_code, 302)   # redirect to home
        self.book.refresh_from_db()
        self.assertTrue(self.book.is_published)

    # 7. multiple perms required: must have ALL
    def test_needs_all_permissions(self):
        self.assertEqual(self.get(self.viewer, "/export/").status_code, 403)  # has view only
        self.viewer.user_permissions.add(
            Permission.objects.get(codename="export_book"))
        # permission cache gotcha: reload user from DB
        viewer = User.objects.get(pk=self.viewer.pk)
        self.assertEqual(self.get(viewer, "/export/").status_code, 200)

    # 8. superuser has everything
    def test_superuser_has_all(self):
        self.assertTrue(self.superuser.has_perm("library.publish_book"))
        self.assertTrue(self.superuser.has_perm("anything.at_all"))
        self.assertEqual(self.get(self.superuser, "/books/").status_code, 200)

    # 9. is_staff is NOT a permission; it only allows admin login
    def test_staff_is_not_permission(self):
        self.assertEqual(self.get(self.staff, "/staff/").status_code, 200)
        self.assertFalse(self.staff.has_perm("library.view_book"))

    # 10. inactive user has no permissions at all
    def test_inactive_user_denied(self):
        u = User.objects.get(pk=self.viewer.pk)
        u.is_active = False
        u.save()
        self.assertFalse(u.has_perm("library.view_book"))

    # 11. UserPassesTestMixin
    def test_superuser_only_view(self):
        self.assertEqual(self.get(self.nobody, "/superuser/").status_code, 403)
        self.assertEqual(self.get(self.superuser, "/superuser/").status_code, 200)

    # 12. object-level (manual): owner OK, stranger denied
    def test_object_level_owner_check(self):
        url = f"/books/{self.book.pk}/edit/"
        self.assertEqual(self.get(self.owner, url).status_code, 200)
        self.assertEqual(self.get(self.nobody, url).status_code, 403)

    # 13. CBV PermissionRequiredMixin (POST)
    def test_delete_requires_permission(self):
        self.client.force_login(self.nobody)
        self.assertEqual(self.client.post(f"/books/{self.book.pk}/delete/").status_code, 403)
        self.nobody.user_permissions.add(Permission.objects.get(codename="delete_book"))
        nobody = User.objects.get(pk=self.nobody.pk)
        self.client.force_login(nobody)
        self.assertEqual(self.client.post(f"/books/{self.book.pk}/delete/").status_code, 302)

    # 14. permission cache gotcha
    def test_permission_cache_gotcha(self):
        u = User.objects.get(pk=self.nobody.pk)
        self.assertFalse(u.has_perm("library.view_book"))          # cached now
        u.user_permissions.add(Permission.objects.get(codename="view_book"))
        self.assertFalse(u.has_perm("library.view_book"))          # STALE!
        u = User.objects.get(pk=u.pk)                              # re-fetch
        self.assertTrue(u.has_perm("library.view_book"))

    # 15. template `perms`
    def test_template_perms(self):
        r = self.get(self.publisher, "/")
        self.assertContains(r, "Publish books")
        self.assertNotContains(r, "Add books")


class LoginLogoutFlow(TestCase):
    def test_nonstaff_login_logout_redirects_home(self):
        User.objects.create_user("viewer2", password="test1234")  # is_staff=False
        r = self.client.post("/login/", {"username": "viewer2", "password": "test1234"})
        self.assertRedirects(r, "/", fetch_redirect_response=False)
        self.assertContains(self.client.get("/"), "Log out")
        r = self.client.post("/logout/")
        self.assertRedirects(r, "/", fetch_redirect_response=False)
        page = self.client.get("/")
        self.assertContains(page, "You are not logged in")
        self.assertNotContains(page, "viewer2")

    def test_inactive_user_cannot_login(self):
        User.objects.create_user("ghost", password="test1234", is_active=False)
        r = self.client.post("/login/", {"username": "ghost", "password": "test1234"})
        self.assertEqual(r.status_code, 200)  # form re-shown with error


class AddBookFlow(TestCase):
    @classmethod
    def setUpTestData(cls):
        def p(code):
            return Permission.objects.get(codename=code, content_type__app_label="library")
        cls.editor = User.objects.create_user("ed", password="x")        # add only
        cls.editor.user_permissions.add(p("add_book"))
        cls.publisher = User.objects.create_user("pub", password="x")    # add + publish
        cls.publisher.user_permissions.add(p("add_book"), p("publish_book"))
        cls.viewer = User.objects.create_user("vw", password="x")
        cls.admin = User.objects.create_superuser("adm", password="x")

    def create(self, user, publish_now):
        self.client.force_login(user)
        data = {"title": "New", "author": "Me", "genre": "tech", "description": "d"}
        if publish_now:
            data["publish_now"] = "on"
        return self.client.post("/books/add/", data)

    def test_no_add_permission_is_403(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get("/books/add/").status_code, 403)

    def test_add_only_user_creates_draft_even_if_checkbox_forged(self):
        self.assertEqual(self.create(self.editor, True).status_code, 302)
        self.assertFalse(Book.objects.get(title="New").is_published)

    def test_publisher_can_create_and_publish(self):
        self.create(self.publisher, True)
        b = Book.objects.get(title="New")
        self.assertTrue(b.is_published)
        self.assertEqual(b.owner, self.publisher)

    def test_admin_can_create_and_publish(self):
        self.create(self.admin, True)
        self.assertTrue(Book.objects.get(title="New").is_published)


class BookDetailFlow(TestCase):
    @classmethod
    def setUpTestData(cls):
        def p(code):
            return Permission.objects.get(codename=code, content_type__app_label="library")
        cls.owner = User.objects.create_user("own", password="x")
        cls.viewer = User.objects.create_user("vw", password="x")
        cls.viewer.user_permissions.add(p("view_book"))
        cls.nobody = User.objects.create_user("nb", password="x")
        cls.publisher = User.objects.create_user("pb", password="x")
        cls.publisher.user_permissions.add(p("view_book"), p("publish_book"))
        cls.pub_book = Book.objects.create(title="Pub", author="A", owner=cls.owner,
                                           is_published=True, description="Hello world", isbn="123")
        cls.draft = Book.objects.create(title="Draft", author="A", owner=cls.owner)

    def test_anonymous_redirected_to_login(self):
        r = self.client.get(f"/books/{self.pub_book.pk}/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r["Location"])

    def test_needs_view_permission(self):
        self.client.force_login(self.nobody)
        self.assertEqual(self.client.get(f"/books/{self.pub_book.pk}/").status_code, 403)

    def test_viewer_sees_published_book_details(self):
        self.client.force_login(self.viewer)
        r = self.client.get(f"/books/{self.pub_book.pk}/")
        self.assertContains(r, "Hello world")
        self.assertContains(r, "123")
        self.assertNotContains(r, "Unpublish</button>")   # no publish perm -> no button

    def test_viewer_cannot_see_draft(self):
        self.client.force_login(self.viewer)
        r = self.client.get(f"/books/{self.draft.pk}/")
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, "still a draft", status_code=403)

    def test_owner_and_publisher_can_see_draft(self):
        self.owner.user_permissions.add(Permission.objects.get(codename="view_book"))
        for u in (User.objects.get(pk=self.owner.pk), self.publisher):
            self.client.force_login(u)
            self.assertEqual(self.client.get(f"/books/{self.draft.pk}/").status_code, 200)

    def test_publish_from_detail_returns_to_detail(self):
        self.client.force_login(self.publisher)
        url = f"/books/{self.draft.pk}/"
        r = self.client.post(f"/books/{self.draft.pk}/publish/", {"next": url})
        self.assertRedirects(r, url, fetch_redirect_response=False)

    def test_external_next_is_ignored(self):
        self.client.force_login(self.publisher)
        r = self.client.post(f"/books/{self.draft.pk}/publish/", {"next": "https://evil.example/"})
        self.assertRedirects(r, "/", fetch_redirect_response=False)

    def test_no_slash_url_redirects(self):
        self.client.force_login(self.viewer)
        r = self.client.get(f"/books/{self.pub_book.pk}")
        self.assertEqual(r.status_code, 301)


class EditBookFlow(TestCase):
    @classmethod
    def setUpTestData(cls):
        def p(code):
            return Permission.objects.get(codename=code, content_type__app_label="library")
        cls.owner = User.objects.create_user("own", password="x")          # no change_book
        cls.stranger = User.objects.create_user("str", password="x")       # no perms
        cls.editor = User.objects.create_user("edt", password="x")         # change_book
        cls.editor.user_permissions.add(p("change_book"), p("view_book"))
        cls.book = Book.objects.create(title="Old", author="A", owner=cls.owner)

    def data(self, **extra):
        d = {"title": "New title", "author": "A", "genre": "tech", "description": "changed"}
        d.update(extra)
        return d

    def test_owner_can_edit_own_book(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(f"/books/{self.book.pk}/edit/").status_code, 200)
        r = self.client.post(f"/books/{self.book.pk}/edit/", self.data())
        self.assertEqual(r.status_code, 302)
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, "New title")

    def test_stranger_cannot_edit(self):
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(f"/books/{self.book.pk}/edit/").status_code, 403)
        self.assertEqual(self.client.post(f"/books/{self.book.pk}/edit/", self.data()).status_code, 403)
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, "Old")

    def test_change_book_permission_edits_any_book(self):
        self.client.force_login(self.editor)
        self.client.post(f"/books/{self.book.pk}/edit/", self.data())
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, "New title")
        self.assertEqual(self.book.owner, self.owner)          # ownership unchanged

    def test_cannot_forge_owner_or_published_flag(self):
        self.client.force_login(self.owner)
        self.client.post(f"/books/{self.book.pk}/edit/",
                         self.data(is_published="on", owner=self.stranger.pk))
        self.book.refresh_from_db()
        self.assertFalse(self.book.is_published)
        self.assertEqual(self.book.owner, self.owner)

    def test_invalid_form_shows_errors(self):
        self.client.force_login(self.owner)
        r = self.client.post(f"/books/{self.book.pk}/edit/", self.data(title=""))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "This field is required")
