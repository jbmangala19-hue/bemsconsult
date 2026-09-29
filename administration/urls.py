from django.urls import path
from django.views import static
from django.conf import settings
from django.conf.urls.static import static
from . import views
from .management import management_page
from .accounts import parametres, profil

urlpatterns = [
    path('parametres/', parametres, name='parametres'),
    path('profil/', profil, name='profil'),
    path('temoignages/', management_page, {'section': 'temoignages'}, name='temoignages'),
    path('mails/', management_page, {'section': 'mails'}, name='mails'),
    path('notifications/', management_page, {'section': 'notifications'}, name='notifications'),
    path('messages/', management_page, {'section': 'messages'}, name='messages'),
    path('acteurs/', management_page, {'section': 'acteurs'}, name='acteurs'),
    path('abonnes/', management_page, {'section': 'abonnes'}, name='abonnes'),
    path('', views.dashboard, name="dashboard"),
    path('articles/', views.articles, name="articles"),
    path('articles/creer/', views.article_create, name="article_create"),
    path('articles/<int:article_id>/modifier/', views.article_edit, name="article_edit"),
    path('articles/<int:article_id>/supprimer/', views.article_delete, name="article_delete"),
    path('acteurs/utilisateurs/', views.users, name="users"),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)