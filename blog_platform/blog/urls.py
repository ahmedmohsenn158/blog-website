from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Auth endpoints
    path('register/', views.register_view, name='register'),
    path('login/', auth_views.LoginView.as_view(
        template_name='login.html'), name='login'
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Blog endpoints
    path('', views.post_list, name='post_list'),
    path('home/', views.post_list, name='home'),
    path('create/', views.post_create, name='post_create'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('posts/<int:pk>/', views.post_detail, name='post_detail'),
    path('posts/<int:pk>/edit/', views.post_update, name='post_update'),
    path('posts/<int:pk>/delete/', views.post_delete, name='post_delete'),
]