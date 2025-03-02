from django.urls import path

from . import views

urlpatterns = [
    path("", views.IncomingCreate.as_view(), name="webmention"),
    path("<int:pk>", views.IncomingDetail.as_view(), name="incoming-detail"),
]
