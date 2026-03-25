from django.db import models
from django.conf import settings
import os

class ChatSession(models.Model):
    """
    Representa uma sessão de conversa (chat) independente.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sessions')
    titulo = models.CharField(max_length=255, default="Nova Conversa")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-atualizado_em']

    def __str__(self):
        return f"{self.user.username} - {self.titulo} ({self.criado_em.strftime('%d/%m/%Y %H:%M')})"

class ChatMessage(models.Model):
    """
    Armazena o conteúdo de cada mensagem na conversa.
    """
    ROLE_CHOICES = [
        ('user', 'Usuário'),
        ('assistant', 'Anagma IA'),
    ]
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."

class ChatAttachment(models.Model):
    """
    Suporta arquivos PDF, Imagens, Excel, Word, TXT, etc.
    """
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='chat_files/%Y/%m/%d/')
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50) # ex: .pdf, .xlsx
    processado = models.BooleanField(default=False) # Se o RAG já extraiu o conteúdo

    def __str__(self):
        return self.file_name
