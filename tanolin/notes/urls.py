from django.urls import path, re_path, include

from . import views


index_paged = [
    path('', views.IndexView.as_view(), {'page': 1}, name='index'),
    path('page/<int:page>', views.IndexView.as_view(), name='index'),
]

thing_or_list = [
    path('', views.NoteListView.as_view(), name='list'),
    path('<int:pk>', views.NoteDetailView.as_view(), name='detail'),
    path('edit/<int:pk>', views.NoteUpdateView.as_view(), name='update'),
]

series_paged = [
    path('page/<int:page>/', include(thing_or_list), {'drafts': False}),
    path('', include(thing_or_list), {'page': 1, 'drafts': False}),
    path('drafts/page/<int:page>/', include(thing_or_list), {'drafts': True}),
    path('drafts/', include(thing_or_list), {'page': 1, 'drafts': True}),
]

tagged_paged = [
    path('', include(series_paged), {'tags': ''}),
    path('tagged/<tags>/', include(series_paged))
]

app_name = 'notes'
urlpatterns = [
    path('', include(index_paged), {'tags': ''}),
    path('tagged/<tags>/', include(index_paged)),
    path('<slug:series_name>/', include([
        path('', include(tagged_paged)),
        path('new', views.NoteCreateView.as_view(), name='create'),
    ])),
    path('*/', include([
        path('', include(tagged_paged), {'series_name': '*'}),
    ])),
]
