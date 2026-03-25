from django.urls import path
from .views import chat_home, send_message, chat_session, rename_session, delete_session

app_name = 'chat'

urlpatterns = [
    path('', chat_home, name='home'),
    path('send/', send_message, name='send_message'),
    path('s/<int:session_id>/', chat_session, name='session'),
    path('s/<int:session_id>/rename/', rename_session, name='rename_session'),
    path('s/<int:session_id>/delete/', delete_session, name='delete_session'),
]
