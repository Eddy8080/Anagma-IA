import os
import sys
from django.apps import AppConfig


class ChatAiConfig(AppConfig):
    name = 'chat_ai'

    def ready(self):
        import chat_ai.signals  # noqa: F401

        # Não carrega o modelo durante comandos de gerenciamento (migrate, shell, etc.)
        comandos_sem_modelo = {
            'migrate', 'makemigrations', 'collectstatic',
            'shell', 'createsuperuser', 'check', 'test', 'dbshell',
            'revectorizar_biblioteca',
        }
        if len(sys.argv) > 1 and sys.argv[1] in comandos_sem_modelo:
            return

        # No runserver do Django, evita duplo carregamento:
        # o processo PAI (file watcher) não deve carregar — só o processo FILHO (worker HTTP).
        if 'runserver' in sys.argv and not os.environ.get('RUN_MAIN'):
            return

        # Pré-aquece o singleton do motor de IA na inicialização do servidor.
        # Assim o modelo já estará na RAM antes da primeira requisição chegar.
        try:
            from .llm_engine import AnagmaLLMEngine
            AnagmaLLMEngine()
            print("[SISTEMA] --- ANAGMA IA ACORDOU COM SUCESSO NO BOOT ---", flush=True)
        except Exception as e:
            import traceback
            print(f"\n[AVISO] Falha ao pré-aquecer o motor de IA no boot: {e}", flush=True)
            traceback.print_exc()
            print("[AVISO] O servidor iniciará sem o motor de IA pré-carregado.\n", flush=True)
