from django.urls import path

from . import views

urlpatterns = [
    # path("index/", views.index, name="index"),
    path("set_free_proxy/", views.set_free_proxies, name="set_free_proxy"),
    path("author/search/", views.get_authors, name="get_authors"),
    path("author/<str:id>", views.get_author_by_id, name="author_id"),
    path("author/name/", views.get_author_by_name, name="author_google_name"),
    path("author/compact/search/", views.get_authors_compact, name="author_compact"),
    path("pub/<str:query>", views.get_pub_detail, name="pub_detail"),
]