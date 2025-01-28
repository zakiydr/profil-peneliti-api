from django.urls import path

from . import views

# from .views import (
#     GoogleLogin,
#     get_current_user
#     LogoutView
# )


urlpatterns = [
    # path("index/", views.index, name="index"),
    path("search/", views.get_authors, name="get_authors"),
    path("author/<str:id>", views.get_author_by_id, name="author_id"),
    path('auth/google/', views.GoogleLogin.as_view(), name='google_login'),
    path('auth/current-user/', views.get_current_user),
    path('auth/logout/', views.LogoutView.as_view()),

]