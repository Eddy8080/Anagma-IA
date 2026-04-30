import io
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.html import strip_tags


class Command(BaseCommand):
    help = 'Re-extrai todos os documentos aprovados com Docling e re-vetoriza no ChromaDB do zero.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--doc-id',
            type=int,
            default=None,
            help='Re-extrai apenas um documento específico pelo ID.',
        )
        parser.add_argument(
            '--skip-chromadb-reset',
            action='store_true',
            default=False,
            help='Não limpa o ChromaDB antes de re-vetorizar (útil para re-extração parcial).',
        )

    def handle(self, *args, **options):
        from core.models import DocumentoBiblioteca
        from chat_ai.document_processor import AnagmaDocumentProcessor
        from chat_ai.rag_engine import AnagmaRAGEngine

        doc_id = options['doc_id']
        skip_reset = options['skip_chromadb_reset']

        self.stdout.write(self.style.SUCCESS('\n=== Re-extração da Biblioteca de Curadoria ===\n'))

        rag = AnagmaRAGEngine()

        # --- Limpa o ChromaDB ---
        if not skip_reset:
            self.stdout.write('Limpando ChromaDB existente...')
            try:
                resultado = rag.vector_store._collection.get()
                ids_existentes = resultado.get('ids', [])
                if ids_existentes:
                    rag.vector_store._collection.delete(ids=ids_existentes)
                    self.stdout.write(f'  {len(ids_existentes)} vetores removidos.')
                else:
                    self.stdout.write('  ChromaDB já estava vazio.')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Aviso ao limpar ChromaDB: {e}'))

        # --- Seleciona documentos ---
        qs = DocumentoBiblioteca.objects.filter(status='approved').order_by('id')
        if doc_id:
            qs = qs.filter(id=doc_id)

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING('Nenhum documento aprovado encontrado.'))
            return

        self.stdout.write(f'\nRe-extraindo {total} documento(s)...\n')

        sucesso = 0
        falha_arquivo = 0
        falha_extracao = 0
        falha_vetorizacao = 0

        for i, doc in enumerate(qs, 1):
            self.stdout.write(f'[{i:3}/{total}] {doc.nome_arquivo[:65]}')

            # Abre o arquivo físico do storage
            try:
                doc.arquivo.open('rb')
                try:
                    file_bytes = doc.arquivo.read()
                finally:
                    doc.arquivo.close()
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'        ERRO ao abrir arquivo: {e}'))
                falha_arquivo += 1
                continue

            if not file_bytes:
                self.stdout.write(self.style.ERROR('        ERRO: arquivo físico vazio ou ausente.'))
                falha_arquivo += 1
                continue

            # Re-extrai com Docling (ou fallback)
            try:
                texto, meta = AnagmaDocumentProcessor.extrair_texto(io.BytesIO(file_bytes), doc.extensao)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'        ERRO na extração: {e}'))
                falha_extracao += 1
                continue

            if not texto or texto.startswith('Erro'):
                self.stdout.write(self.style.WARNING(
                    f'        AVISO: extracao vazia/erro: {(texto or "vazio")[:80]}'
                ))
                falha_extracao += 1
                continue

            # Atualiza conteúdo no banco
            doc.conteudo_extraido = texto
            doc.processado_em = timezone.now()
            doc.save(update_fields=['conteudo_extraido', 'processado_em'])
            self.stdout.write(f'        Extraídos: {len(texto):,} chars')

            # Vetoriza no ChromaDB
            try:
                texto_limpo = strip_tags(texto)
                ok = rag.vetorizar_texto(texto_limpo, doc.nome_arquivo)
                if ok:
                    self.stdout.write(self.style.SUCCESS('        Vetorizado ✓'))
                    sucesso += 1
                else:
                    self.stdout.write(self.style.WARNING('        AVISO: vetorização retornou False.'))
                    falha_vetorizacao += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'        ERRO na vetorização: {e}'))
                falha_vetorizacao += 1

        # --- Relatório final ---
        self.stdout.write(self.style.SUCCESS(f'\n=== RESULTADO ==='))
        self.stdout.write(f'  Sucesso:              {sucesso}/{total}')
        if falha_arquivo:
            self.stdout.write(self.style.ERROR(f'  Falha (arquivo):      {falha_arquivo}'))
        if falha_extracao:
            self.stdout.write(self.style.WARNING(f'  Falha (extração):     {falha_extracao}'))
        if falha_vetorizacao:
            self.stdout.write(self.style.WARNING(f'  Falha (vetorização):  {falha_vetorizacao}'))

        if sucesso == total:
            self.stdout.write(self.style.SUCCESS('\nTodos os documentos re-extraídos e re-vetorizados com sucesso!\n'))
        else:
            self.stdout.write(self.style.WARNING(
                f'\nAtenção: {total - sucesso} documento(s) com problema. '
                f'Consulte os logs acima.\n'
            ))
