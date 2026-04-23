"""
Management command: revectorizar_biblioteca
============================================
Re-vetoriza no ChromaDB todos os documentos aprovados e correções RLHF
que existiam antes da implementação da busca semântica.

Uso:
    python manage.py revectorizar_biblioteca
    python manage.py revectorizar_biblioteca --apenas-documentos
    python manage.py revectorizar_biblioteca --apenas-rlhf
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Re-vetoriza documentos aprovados e correções RLHF no ChromaDB.'

    def add_arguments(self, parser):
        parser.add_argument('--apenas-documentos', action='store_true')
        parser.add_argument('--apenas-rlhf', action='store_true')

    def handle(self, *args, **options):
        from chat_ai.llm_engine import AnagmaLLMEngine
        from core.models import DocumentoBiblioteca
        from chat_ai.models import AIConsistencyCorrection

        rag = AnagmaLLMEngine().rag
        so_docs = options['apenas_documentos']
        so_rlhf = options['apenas_rlhf']

        if not so_rlhf:
            docs = DocumentoBiblioteca.objects.filter(status='approved').exclude(conteudo_extraido='')
            total = docs.count()
            self.stdout.write(f'Vetorizando {total} documentos aprovados...')
            ok = 0
            for doc in docs:
                try:
                    rag.vetorizar_texto(doc.conteudo_extraido, doc.nome_arquivo)
                    ok += 1
                    self.stdout.write(f'  ✓ {doc.nome_arquivo}')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ✗ {doc.nome_arquivo}: {e}'))
            self.stdout.write(self.style.SUCCESS(f'Documentos: {ok}/{total} vetorizados.'))

        if not so_docs:
            correcoes = (
                AIConsistencyCorrection.objects
                .filter(is_integrated=False)
                .exclude(user_query='')
                .exclude(suggested_improvement='')
            )
            total = correcoes.count()
            self.stdout.write(f'Vetorizando {total} correções RLHF pendentes...')
            ok = 0
            for cor in correcoes:
                try:
                    titulo = cor.titulo_melhoria or f"RLHF-{cor.id}"
                    texto = f"Pergunta: {cor.user_query}\nResposta ideal: {cor.suggested_improvement}"
                    rag.vetorizar_texto(texto, f"RLHF:{titulo}")
                    cor.is_integrated = True
                    cor.save(update_fields=['is_integrated'])
                    ok += 1
                    self.stdout.write(f'  ✓ {titulo}')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ✗ RLHF-{cor.id}: {e}'))
            self.stdout.write(self.style.SUCCESS(f'Correções RLHF: {ok}/{total} vetorizadas.'))
