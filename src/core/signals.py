import threading
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from django.utils.html import strip_tags
from .models import GlobalIdeia, DocumentoBiblioteca

# Dicionário em memória para detectar transições de estado sem campo extra no banco
_estado_anterior = {}


def _obter_rag():
    """Reutiliza o RAG do singleton LLM se já estiver na RAM; cria standalone caso contrário."""
    try:
        from chat_ai.llm_engine import AnagmaLLMEngine
        if AnagmaLLMEngine._instance is not None:
            return AnagmaLLMEngine._instance.rag
    except Exception:
        pass
    from chat_ai.rag_engine import AnagmaRAGEngine
    return AnagmaRAGEngine()


def _vetorizar_em_thread(texto, source_name):
    """Executa a vetorização em background para não bloquear a requisição do admin."""
    def _executar():
        try:
            rag = _obter_rag()
            rag.vetorizar_texto(texto, source_name)
            print(f"[RAG Signal] Vetorizado com sucesso: {source_name}", flush=True)
        except Exception as e:
            print(f"[RAG Signal] Erro ao vetorizar '{source_name}': {e}", flush=True)

    threading.Thread(target=_executar, daemon=True).start()


# ---------------------------------------------------------------------------
# GlobalIdeia — invalida cache e vetoriza quando ativada
# ---------------------------------------------------------------------------

@receiver(post_save, sender=GlobalIdeia)
@receiver(post_delete, sender=GlobalIdeia)
def invalidar_cache_ideias(sender, **kwargs):
    cache.delete('global_ideias')


@receiver(pre_save, sender=GlobalIdeia)
def capturar_ativa_anterior(sender, instance, **kwargs):
    """Captura se a ideia estava ativa ANTES do save para detectar a transição."""
    if instance.pk:
        try:
            _estado_anterior[f'ideia_{instance.pk}'] = (
                GlobalIdeia.objects.values_list('ativa', flat=True).get(pk=instance.pk)
            )
        except GlobalIdeia.DoesNotExist:
            pass


@receiver(post_save, sender=GlobalIdeia)
def vetorizar_ideia_ativa(sender, instance, created, **kwargs):
    """Vetoriza a ideia no ChromaDB apenas quando ela é ativada pela primeira vez."""
    chave = f'ideia_{instance.pk}'
    ativa_anterior = _estado_anterior.pop(chave, None)

    if not instance.ativa or not instance.conteudo:
        return

    # Só dispara na transição False/None → True (não re-vetoriza se já era ativa)
    if not created and ativa_anterior is True:
        return

    # Formatação Markdown estruturada para consistência com o motor Docling
    texto = (
        f"# ORIENTAÇÃO INTERNA (Anagma): {instance.titulo}\n\n"
        f"**Procedimento / Regra Interna:**\n{strip_tags(instance.conteudo)}"
    )
    _vetorizar_em_thread(texto, f"Ideia:{instance.id}:{instance.titulo[:60]}")


# ---------------------------------------------------------------------------
# DocumentoBiblioteca — vetoriza quando aprovado
# ---------------------------------------------------------------------------

@receiver(pre_save, sender=DocumentoBiblioteca)
def capturar_status_anterior(sender, instance, **kwargs):
    """Captura o status ANTES do save para detectar a transição para 'approved'."""
    if instance.pk:
        try:
            _estado_anterior[f'doc_{instance.pk}'] = (
                DocumentoBiblioteca.objects.values_list('status', flat=True).get(pk=instance.pk)
            )
        except DocumentoBiblioteca.DoesNotExist:
            pass


@receiver(post_save, sender=DocumentoBiblioteca)
def vetorizar_documento_aprovado(sender, instance, created, **kwargs):
    """Vetoriza o documento no ChromaDB apenas quando o status muda para 'approved'."""
    chave = f'doc_{instance.pk}'
    status_anterior = _estado_anterior.pop(chave, None)

    if instance.status != 'approved' or not instance.conteudo_extraido:
        return

    # Só dispara na transição pending/rejected → approved (não re-vetoriza)
    if not created and status_anterior == 'approved':
        return

    _vetorizar_em_thread(
        instance.conteudo_extraido,
        f"Bib:{instance.id}:{instance.nome_arquivo}"
    )
