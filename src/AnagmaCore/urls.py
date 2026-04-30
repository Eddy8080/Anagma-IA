from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from core.views import biblioteca_catalogo

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('core.urls')),
    path('chat/', include('chat_ai.urls')),
    path('admin-panel/', include('core.urls_admin')),
    path('biblioteca/', biblioteca_catalogo, name='biblioteca'),
    path('', RedirectView.as_view(url='chat/')),
]
