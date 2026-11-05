from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", LoginView.as_view(template_name="library/login.html"), name="login"),
    path("logout/", LogoutView.as_view(next_page="/"), name="logout"),
    path("dashboard/", views.dashboard),
    path("books/", views.book_list),
    path("books/add/", views.add_book, name="add_book"),
    path("books/<int:pk>/", views.book_detail, name="book_detail"),
    path("books/<int:pk>/publish/", views.publish_book, name="publish_book"),
    path("books/<int:pk>/unpublish/", views.unpublish_book, name="unpublish_book"),
    path("books/<int:pk>/edit/", views.edit_book, name="edit_book"),
    path("books/<int:pk>/delete/", views.BookDeleteView.as_view()),
    path("export/", views.export_books),
    path("staff/", views.staff_only),
    path("superuser/", views.SuperuserOnlyView.as_view()),
    path("me/", views.my_permissions, name="my_permissions"),
]
