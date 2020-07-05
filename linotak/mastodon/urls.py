"""URLconf for Mastodon."""


from django.urls import path

from . import views

app_name = 'mastodon'
urlpatterns = [
    path('connections/add', views.ConnectionCreateView.as_view(), name='connection-create'),
    path('callback', views.callback, name='callback'),
    path('connections/<int:pk>', views.ConnectionDetailView.as_view(), name='connection-detail'),
]
