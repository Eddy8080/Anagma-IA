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
    password_change_required = models.BooleanField(default=False, help_text="Obriga o usuário a trocar a senha no próximo login.")
    
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
    texto = models.TextField(default="""1. IDENTIDADE: Você é a Digiana, a inteligência oficial e autoridade técnica em Contabilidade Brasileira e Internacional.
2. TOM DE VOZ: Assertivo, técnico, profissional e proativo. Evite 'eu recomendaria', use 'A análise técnica indica'.
3. IDIOMA: Responda EXCLUSIVAMENTE em Português Brasileiro (PT-BR).
4. FOCO: Domínio contábil, fiscal e tributário. Recuse temas irrelevantes.
5. CONFORMIDADE: Baseie-se sempre nas normas da Receita Federal e IFRS.

6. CONTEXTO INSTITUCIONAL (FUNDAÇÃO):
* ORIGEM: Nossa trajetória iniciou como Anagma, uma consultoria focada em inovação contábil.
* EVOLUÇÃO: Em 2026, consolidamos nossa maturidade tecnológica e mudamos oficialmente nossa identidade para Digiana.
* PROPÓSITO: Esta mudança reflete nossa essência — a fusão da sabedoria contábil com a inteligência digital de ponta.
* POSICIONAMENTO: Somos o cérebro digital que apoia empresas brasileiras no Brasil e no exterior.""")
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Perfil Cultural Digiana'
        verbose_name_plural = 'Perfil Cultural Digiana'

    def __str__(self):
        return 'Perfil Cultural Digiana'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class GlobalIdeia(models.Model):
    """
    Representa as 'ideias solidificadas' que ajudam a todos os usuários.
    """
    titulo = models.CharField(max_length=255)
    conteudo = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)
    autor = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    ativa = models.BooleanField(default=False)

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
    enviado_por = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='documentos_enviados')
    auditado_por = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='documentos_auditados')
    motivo_rejeicao = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Documento da Biblioteca'
        verbose_name_plural = 'Documentos da Biblioteca'
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.nome_arquivo} ({self.get_status_display()})"


class ConfiguracaoIA(models.Model):
    """
    Singleton para gerenciar qual cérebro a Digiana está usando e o status do carregamento.
    """
    MODELO_CHOICES = [
        ('LEVE', 'Digiana - LEVE (GGUF)'),
        ('COMPLETO', 'Digiana - COMPLETO (Safetensors)'),
    ]
    
    STATUS_CHOICES = [
        ('PRONTO', 'Pronto para Uso'),
        ('CARREGANDO', 'Carregando...'),
        ('ERRO', 'Erro no Carregamento'),
        ('HIBERNACAO', 'Em Hibernação (Fallback)'),
    ]

    modelo_preferido = models.CharField(max_length=10, choices=MODELO_CHOICES, default='LEVE')
    modelo_em_uso = models.CharField(max_length=10, choices=MODELO_CHOICES, default='LEVE')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PRONTO')
    
    etapa_nome = models.CharField(max_length=100, default='Sistema Estável', help_text="Mensagem amigável para o Admin")
    progresso = models.IntegerField(default=100, help_text="0 a 100 para a barra de progresso")
    
    ultimo_erro = models.TextField(blank=True, null=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuração da IA'
        verbose_name_plural = 'Configurações da IA'

    def __str__(self):
        return f"IA: {self.modelo_em_uso} ({self.status})"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
