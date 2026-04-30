from django.urls import path
from .views import (
    chat_home, send_message, chat_stream, chat_session, rename_session,
    delete_session, pin_session, message_feedback, upload_document,
    meus_envios, get_session_messages
)

app_name = 'chat'

urlpatterns = [
    path('', chat_home, name='home'),
    path('send/', send_message, name='send_message'),
    path('stream/', chat_stream, name='chat_stream'),
    path('upload/', upload_document, name='upload_document'),
    path('s/<int:session_id>/', chat_session, name='session'),
    path('s/<int:session_id>/messages/', get_session_messages, name='get_session_messages'),
    path('s/<int:session_id>/rename/', rename_session, name='rename_session'),
    path('s/<int:session_id>/delete/', delete_session, name='delete_session'),
    path('s/<int:session_id>/pin/', pin_session, name='pin_session'),
    path('msg/<int:message_id>/feedback/', message_feedback, name='message_feedback'),
    path('meus-envios/', meus_envios, name='meus_envios'),
]
