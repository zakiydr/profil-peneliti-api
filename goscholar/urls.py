from django.urls import path

from . import views

urlpatterns = [
    # path("index/", views.index, name="index"),
    path("search/", views.get_authors, name="get_authors"),
    path("author/<str:id>", views.get_author_by_id, name="author_id"),
    path("author/name/", views.get_author_by_google, name="author_google_name"),
    path("search/compact/", views.get_authors_compact, name="author_compact"),
]