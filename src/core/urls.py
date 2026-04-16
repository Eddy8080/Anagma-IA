from django.urls import path, include
from django.contrib.auth import views as auth_views
from .views import register_view, AnagmaLoginView, logout_view, criar_ideia, force_password_change

urlpatterns = [
    path('login/', AnagmaLoginView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),
    path('register/', register_view, name='register'),
    path('ideia/criar/', criar_ideia, name='criar_ideia'),
    path('force-password-change/', force_password_change, name='force_password_change'),
    
    # Password Reset
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
]
