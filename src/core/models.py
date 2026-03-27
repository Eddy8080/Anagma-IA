from django.contrib.auth.models import AbstractUser
from django.db import models
from datetime import datetime

class CustomUser(AbstractUser):
    """
    Modelo de usuário customizado para o Banco de Ideias.
    Permite saudações personalizadas e identificação clara.
    """
    STATUS_CHOICES = [
        ('active', 'Ativo'),
        ('inactive', 'Inativo'),
        ('paused', 'Pausado'),
    ]
    nome_completo = models.CharField(max_length=255, blank=True)
    account_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    
    class Meta:
        ordering = ['nome_completo', 'username']

    def get_saudacao(self):
        hora = datetime.now().hour
        if 5 <= hora < 12:
            return "Bom dia"
        elif 12 <= hora < 18:
            return "Boa tarde"
        else:
            return "Boa noite"

    def __str__(self):
        return self.username

class PerfilAnagma(models.Model):
    """Singleton — perfil cultural da empresa que dá tom às respostas da IA."""
    texto = models.TextField()
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Perfil Anagma'

    def __str__(self):
        return 'Perfil Anagma'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={'texto': ''})
        return obj


class GlobalIdeia(models.Model):
    """
    Representa as 'ideias solidificadas' que ajudam a todos os usuários.
    """
    titulo = models.CharField(max_length=255)
    conteudo = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)
    autor = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    ativa = models.BooleanField(default=True)

    def __str__(self):
        return self.titulo

class DocumentoBiblioteca(models.Model):
    """
    Central de Inteligência Documental. Armazena arquivos para auditoria e aprendizado da IA.
    """
    STATUS_CHOICES = [
        ('pending', 'Pendente de Auditoria'),
        ('approved', 'Aprovado (Na Memória)'),
        ('rejected', 'Rejeitado (Conteúdo Irrelevante)'),
    ]

    nome_arquivo = models.CharField(max_length=255)
    arquivo = models.FileField(upload_to='biblioteca/documentos/')
    extensao = models.CharField(max_length=10)
    conteudo_extraido = models.TextField(blank=True, help_text="Texto bruto extraído via OCR/Parsing")
    resumo_ia = models.TextField(blank=True, help_text="Resumo inicial gerado pela IA para triagem")
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    
    criado_em = models.DateTimeField(auto_now_add=True)
    processado_em = models.DateTimeField(null=True, blank=True)
    auditado_por = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='documentos_auditados')
    motivo_rejeicao = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Documento da Biblioteca'
        verbose_name_plural = 'Documentos da Biblioteca'
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.nome_arquivo} ({self.get_status_display()})"
