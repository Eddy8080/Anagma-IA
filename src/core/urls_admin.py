from django.urls import path
from .views import (
    admin_panel,
    admin_usuarios,
    admin_criar_usuario,
    admin_deletar_usuario,
    admin_update_user_status,
    admin_ideias,
    admin_criar_ideia,
    admin_deletar_ideia,
    admin_toggle_ideia,
    admin_editar_ideia,
    admin_perfil_anagma,
    admin_biblioteca,
    admin_upload_biblioteca,
    admin_auditar_documento,
    admin_deletar_documento,
    admin_feedback_list,
    admin_feedback_messages,
    admin_save_correction,
    admin_deletar_feedback,
    admin_modelos,
    admin_ia_status,
)

app_name = 'admin_panel'

urlpatterns = [
    path('', admin_panel, name='dashboard'),
    path('usuarios/', admin_usuarios, name='usuarios'),
    path('usuarios/criar/', admin_criar_usuario, name='criar_usuario'),
    path('usuarios/<int:user_id>/deletar/', admin_deletar_usuario, name='deletar_usuario'),
    path('usuarios/<int:user_id>/status/', admin_update_user_status, name='update_user_status'),
    
    path('ideias/', admin_ideias, name='ideias'),
    path('ideias/criar/', admin_criar_ideia, name='criar_ideia'),
    path('ideias/<int:ideia_id>/editar/', admin_editar_ideia, name='editar_ideia'),
    path('ideias/<int:ideia_id>/deletar/', admin_deletar_ideia, name='deletar_ideia'),
    path('ideias/<int:ideia_id>/toggle/', admin_toggle_ideia, name='toggle_ideia'),
    
    path('perfil/', admin_perfil_anagma, name='perfil_anagma'),

    # Biblioteca de Curadoria
    path('biblioteca/', admin_biblioteca, name='biblioteca'),
    path('biblioteca/upload/', admin_upload_biblioteca, name='upload_biblioteca'),
    path('biblioteca/<int:doc_id>/auditar/', admin_auditar_documento, name='auditar_documento'),
    path('biblioteca/<int:doc_id>/deletar/', admin_deletar_documento, name='deletar_documento'),

    # Feedback e Curadoria IA
    path('feedback/<str:tipo>/', admin_feedback_list, name='feedback_list'),
    path('feedback/user/<int:user_id>/<str:tipo>/', admin_feedback_messages, name='feedback_messages'),
    path('feedback/message/<int:message_id>/save/', admin_save_correction, name='save_correction'),
    path('feedback/message/<int:message_id>/delete/', admin_deletar_feedback, name='deletar_feedback'),

    # Gestão de Modelos de IA
    path('modelos/', admin_modelos, name='modelos'),
    path('ia-status/', admin_ia_status, name='ia_status'),
]
