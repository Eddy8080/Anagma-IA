from django.urls import path
from .views import (
    admin_panel,
    admin_usuarios,
    admin_criar_usuario,
    admin_deletar_usuario,
    admin_toggle_ativo,
    admin_toggle_superuser,
    admin_ideias,
    admin_deletar_ideia,
    admin_toggle_ideia,
    admin_perfil_anagma,
)

app_name = 'admin_panel'

urlpatterns = [
    path('', admin_panel, name='dashboard'),
    path('usuarios/', admin_usuarios, name='usuarios'),
    path('usuarios/criar/', admin_criar_usuario, name='criar_usuario'),
    path('usuarios/<int:user_id>/deletar/', admin_deletar_usuario, name='deletar_usuario'),
    path('usuarios/<int:user_id>/ativo/', admin_toggle_ativo, name='toggle_ativo'),
    path('usuarios/<int:user_id>/toggle/', admin_toggle_superuser, name='toggle_superuser'),
    path('ideias/', admin_ideias, name='ideias'),
    path('ideias/<int:ideia_id>/deletar/', admin_deletar_ideia, name='deletar_ideia'),
    path('ideias/<int:ideia_id>/toggle/', admin_toggle_ideia, name='toggle_ideia'),
    path('perfil/', admin_perfil_anagma, name='perfil_anagma'),
]
