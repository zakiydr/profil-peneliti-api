from django.urls import path

from . import views

urlpatterns = [
    # path("index/", views.index, name="index"),
    path("search/", views.get_authors, name="get_authors"),
    # path("author/<str:id>", views.get_author_by_id, name="author_id"),
]