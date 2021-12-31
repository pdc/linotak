from django.urls import path

from . import views


app_name = "about"
urlpatterns = [
    path("", views.page_view, name="index"),
    path("<slug:name>", views.page_view, name="page"),
]
