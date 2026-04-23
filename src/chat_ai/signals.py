import threading
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import AIConsistencyCorrection


def _obter_rag():
    """Reutiliza o RAG do singleton LLM se já estiver na RAM; cria standalone caso contrário."""
    try:
        from .llm_engine import AnagmaLLMEngine
        if AnagmaLLMEngine._instance is not None:
            return AnagmaLLMEngine._instance.rag
    except Exception:
        pass
    from .rag_engine import AnagmaRAGEngine
    return AnagmaRAGEngine()


@receiver(post_save, sender=AIConsistencyCorrection)
def vetorizar_correcao_rlhf(sender, instance, created, **kwargs):
    """
    Vetoriza correções RLHF no ChromaDB imediatamente após serem salvas.
    Usa update() em vez de save() para não re-disparar o signal.
    """
    if instance.is_integrated:
        return
    if not instance.user_query or not instance.suggested_improvement:
        return

    def _executar():
        try:
            rag = _obter_rag()
            titulo = instance.titulo_melhoria or f"RLHF-{instance.id}"
            texto = (
                f"Pergunta: {instance.user_query}\n"
                f"Resposta ideal: {instance.suggested_improvement}"
            )
            rag.vetorizar_texto(texto, f"RLHF:{titulo}")
            # update() em vez de save() para não re-disparar este signal
            AIConsistencyCorrection.objects.filter(pk=instance.pk).update(is_integrated=True)
            print(f"[RAG Signal] RLHF vetorizado: {titulo}", flush=True)
        except Exception as e:
            print(f"[RAG Signal] Erro ao vetorizar RLHF {instance.id}: {e}", flush=True)

    threading.Thread(target=_executar, daemon=True).start()
