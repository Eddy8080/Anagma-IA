from django.db import models
from django.conf import settings
import os

class ChatSession(models.Model):
    """
    Representa uma sessão de conversa (chat) independente.
    Soft delete: deleted_at preserva o histórico e o aprendizado da IA.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions')
    titulo = models.CharField(max_length=255, default="Nova Conversa")
    pinned = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_sessions')

    class Meta:
        ordering = ['-atualizado_em']

    def __str__(self):
        user_name = self.user.username if self.user else "Anônimo/Ex-Colaborador"
        return f"{user_name} - {self.titulo} ({self.criado_em.strftime('%d/%m/%Y %H:%M')})"

class ChatMessage(models.Model):
    """
    Armazena o conteúdo de cada mensagem na conversa.
    """
    ROLE_CHOICES = [
        ('user', 'Usuário'),
        ('assistant', 'Anagma IA'),
    ]
    session = models.ForeignKey(ChatSession, on_delete=models.SET_NULL, null=True, blank=True, related_name='messages')
    FEEDBACK_CHOICES = [('like', 'Curtiu'), ('dislike', 'Não curtiu')]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    feedback = models.CharField(max_length=10, choices=FEEDBACK_CHOICES, null=True, blank=True)
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

class AIConsistencyCorrection(models.Model):
    """
    Modelo de Curadoria (RLHF): Armazena as correções dos Superusuários 
    para as respostas que receberam feedback negativo ou positivo.
    """
    # Alterado de OneToOneField para ForeignKey para evitar erros de restrição no SQLite 
    # ao lidar com exclusões em massa e garantir integridade referencial SET_NULL.
    message = models.ForeignKey(ChatMessage, on_delete=models.SET_NULL, null=True, blank=True, related_name='corrections')
    titulo_melhoria = models.CharField(max_length=255, blank=True, help_text="Título resumido para organização (ex: Regra de IRPJ).")
    user_query = models.TextField(blank=True, help_text="Pergunta original do usuário para contexto perpétuo.")
    original_response = models.TextField(help_text="Cópia da resposta original da IA para auditoria.")
    suggested_improvement = models.TextField(help_text="Resposta ideal escrita pelo Superusuário.")
    curated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='curated_corrections')
    curated_at = models.DateTimeField(auto_now_add=True)
    is_integrated = models.BooleanField(default=False, help_text="Marcar quando o RAG absorver esta melhoria.")

    class Meta:
        verbose_name = "Correção de Consistência IA"
        verbose_name_plural = "Correções de Consistência IA"
        ordering = ['-curated_at']

    def __str__(self):
        prefixo = f"Correção: {self.titulo_melhoria}" if self.titulo_melhoria else f"Correção #{self.id}"
        if self.message and self.message.session and self.message.session.user:
            return f"{prefixo} (Usuário: {self.message.session.user.username})"
        return f"{prefixo} (Histórico Original Excluído)"
