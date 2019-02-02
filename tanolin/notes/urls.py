from django.urls import path, include

from . import views

app_name = 'notes'
urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('tagged/<tags>', views.IndexView.as_view(), name='index'),
    path('<slug:series_name>/', include([
        path('', views.NoteListView.as_view(), name='list'),
        path('tagged/<tags>', views.NoteListView.as_view(), name='list'),
        path('new', views.NoteCreateView.as_view(), name='create'),
        path('<int:pk>', views.NoteDetailView.as_view(), name='detail'),
        path('<int:pk>/edit', views.NoteUpdateView.as_view(), name='update'),
    ])),
]
