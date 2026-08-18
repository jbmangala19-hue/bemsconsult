from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name="home"),
    path('blog/', views.blog, name="blog"),
    path('cabinet/', views.cabinet, name="cabinet"),
    path('contact/', views.contact, name="contact"),
    path('services/', views.services, name="services"),
]