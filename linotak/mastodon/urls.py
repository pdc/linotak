"""URLconf for Mastodon."""


from django.urls import path

from . import views

app_name = 'mastodon'
urlpatterns = [
    path('callback', views.callback, name='callback'),
]
