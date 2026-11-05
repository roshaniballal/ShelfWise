from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand

from library.models import Book

PASSWORD = "test1234"


class Command(BaseCommand):
    help = "Create demo users, groups and books to experiment with permissions"

    def handle(self, *args, **opts):
        def perm(codename):
            return Permission.objects.get(codename=codename, content_type__app_label="library")

        # ---- GROUPS (a reusable bundle of permissions) ----
        viewers, _ = Group.objects.get_or_create(name="Viewers")
        viewers.permissions.set([perm("view_book")])

        editors, _ = Group.objects.get_or_create(name="Editors")
        editors.permissions.set([perm("view_book"), perm("add_book"), perm("change_book")])

        publishers, _ = Group.objects.get_or_create(name="Publishers")
        publishers.permissions.set([perm("view_book"), perm("add_book"), perm("publish_book"), perm("export_book")])

        def make(username, **extra):
            u, _ = User.objects.get_or_create(username=username, defaults=extra)
            for k, v in extra.items():
                setattr(u, k, v)
            u.set_password(PASSWORD)
            u.save()
            return u

        # ---- USERS ----
        make("anon_like")                                      # logged in, zero permissions
        make("viewer").groups.set([viewers])                   # permission via GROUP
        make("editor", is_staff=True).groups.set([editors])    # staff + group (can enter admin)
        make("publisher").groups.set([publishers])
        direct = make("direct_perm")                           # permission assigned DIRECTLY to user
        direct.user_permissions.set([perm("view_book"), perm("delete_book")])
        make("inactive", is_active=False)                      # is_active=False -> all perms denied
        make("admin", is_staff=True, is_superuser=True)        # superuser = has EVERY permission

        # ---- BOOKS ----
        owners = {u.username: u for u in User.objects.all()}
        demo_books = [
            dict(title="Django for Beginners", author="W. Vincent", owner="editor", is_published=True,
                 genre="tech", isbn="9780000000011", page_count=320, publication_year=2022,
                 description="A step-by-step introduction to building web apps with Django.\nCovers models, views, templates and deployment."),
            dict(title="Two Scoops of Django", author="Greenfeld", owner="admin", is_published=False,
                 genre="tech", isbn="9780000000028", page_count=530, publication_year=2020,
                 description="Best practices and patterns for professional Django projects."),
            dict(title="Cosmos", author="C. Sagan", owner="admin", is_published=True,
                 genre="science", isbn="9780000000066", page_count=396, publication_year=1980,
                 description="A tour of the universe and of the people who learned how to read it."),
            dict(title="The Hobbit", author="J. R. R. Tolkien", owner="editor", is_published=True,
                 genre="fiction", isbn="9780000000073", page_count=310, publication_year=1937,
                 description="A quiet hobbit is pulled into a quest to reclaim a mountain from a dragon."),
            dict(title="Fluent Python", author="L. Ramalho", owner="publisher", is_published=True,
                 genre="tech", isbn="9780000000035", page_count=1012, publication_year=2022,
                 description="A deep dive into Python's features for writing effective, idiomatic code."),
            dict(title="Sapiens", author="Y. N. Harari", owner="publisher", is_published=False,
                 genre="history", isbn="9780000000080", page_count=443, publication_year=2011,
                 description="A short history of humankind, from the first tools to the modern economy."),
            dict(title="Clean Code", author="R. Martin", owner="editor", is_published=False,
                 genre="tech", isbn="9780000000042", page_count=464, publication_year=2008,
                 description="A handbook of agile software craftsmanship (still a draft in this library)."),
            dict(title="Atomic Habits", author="J. Clear", owner="admin", is_published=True,
                 genre="nonfiction", isbn="9780000000059", page_count=320, publication_year=2018,
                 description="Practical strategies to build good habits and break bad ones."),
        ]
        for d in demo_books:
            d = dict(d)
            owner = owners[d.pop("owner")]
            book, created = Book.objects.get_or_create(title=d["title"], defaults={**d, "owner": owner})
            if not created and not book.description:      # fill in details on older databases
                for k in ("description", "genre", "isbn", "page_count", "publication_year"):
                    setattr(book, k, d[k])
                book.save()

        self.stdout.write(self.style.SUCCESS(f"Seeded. All passwords: {PASSWORD}"))
