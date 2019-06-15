from django.urls import path, include

from . import views, feed


thing_or_list = [
    path('', views.NoteListView.as_view(), name='list'),
    path('<int:pk>', views.NoteDetailView.as_view(), name='detail'),
    path('<int:pk>.edit', views.NoteUpdateView.as_view(), name='edit'),
]

series_paged = [
    path('page<int:page>/', include(thing_or_list), {'drafts': False}),
    path('', include(thing_or_list), {'page': 1, 'drafts': False}),
    path('drafts/page<int:page>/', include(thing_or_list), {'drafts': True}),
    path('drafts/', include(thing_or_list), {'page': 1, 'drafts': True}),
    path('atom/page<int:page>/', feed.NoteFeedView.as_view(), {'drafts': False}, name='feed'),
    path('atom/', feed.NoteFeedView.as_view(), {'page': 1, 'drafts': False}, name='feed'),
]

tagged_paged = [
    path('', include(series_paged), {'tags': ''}),
    path('tagged/<tags>/', include(series_paged))
]

app_name = 'notes'
urlpatterns = [
    path('', include(tagged_paged)),
    path('new', views.NoteCreateView.as_view(), name='new'),
]
