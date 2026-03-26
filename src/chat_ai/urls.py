from django.urls import path
from .views import chat_home, send_message, chat_session, rename_session, delete_session, pin_session, message_feedback

app_name = 'chat'

urlpatterns = [
    path('', chat_home, name='home'),
    path('send/', send_message, name='send_message'),
    path('s/<int:session_id>/', chat_session, name='session'),
    path('s/<int:session_id>/rename/', rename_session, name='rename_session'),
    path('s/<int:session_id>/delete/', delete_session, name='delete_session'),
    path('s/<int:session_id>/pin/', pin_session, name='pin_session'),
    path('msg/<int:message_id>/feedback/', message_feedback, name='message_feedback'),
]
