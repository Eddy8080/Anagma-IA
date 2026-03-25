from django.urls import path, include
from .views import register_view, AnagmaLoginView, logout_view, criar_ideia

urlpatterns = [
    path('login/', AnagmaLoginView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),
    path('register/', register_view, name='register'),
    path('ideia/criar/', criar_ideia, name='criar_ideia'),
    path('', include('django.contrib.auth.urls')),
]
