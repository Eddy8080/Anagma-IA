import os
import re
import unicodedata
import pandas as pd
from langchain_community.document_loaders import UnstructuredFileLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from .vocabulario import STOPWORDS_RAG
try:
    from langchain_chroma import Chroma
except ImportError:
    from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from django.conf import settings

class AnagmaRAGEngine:
    """
    Motor de RAG (Retrieval-Augmented Generation) da Anagma IA.
    Especializado em processar documentos contábeis brasileiros.
    """
    def __init__(self, persist_directory=None):
        self.persist_directory = persist_directory or os.path.join(
            settings.BASE_DIR.parent, 'assets', 'vector_store'
        )

        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=200,
            # "\n|" impede que uma linha de tabela markdown seja cortada no meio
            separators=["\n\n\n", "\n\n", "\n|", "\n", " ", ""]
        )

        # Vector store persistido — reutilizado em todas as buscas (sem reconectar a cada chamada)
        self.vector_store = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embeddings
        )

    def processar_arquivo(self, file_path):
        """
        Lê e vetoriza um arquivo contábil.
        Suporta PDF, DOCX, XLSX, CSV, TXT.
        """
        ext = os.path.splitext(file_path)[1].lower()

        try:
            if ext == '.pdf':
                loader = PyPDFLoader(file_path)
            elif ext in ['.xlsx', '.xls', '.csv']:
                df = pd.read_excel(file_path) if ext != '.csv' else pd.read_csv(file_path)
                text = df.to_string()
                from langchain_core.documents import Document
                docs = [Document(page_content=text, metadata={"source": file_path})]
                return self._vetorizar_documentos(docs)
            else:
                loader = UnstructuredFileLoader(file_path)

            docs = loader.load()
            return self._vetorizar_documentos(docs)
        except Exception as e:
            print(f"Erro ao processar {file_path}: {str(e)}")
            return False

    def _vetorizar_documentos(self, docs):
        """
        Adiciona documentos ao ChromaDB existente sem apagar o conteúdo anterior.
        """
        chunks = self.text_splitter.split_documents(docs)
        self.vector_store.add_documents(chunks)
        print(f"[RAG] {len(chunks)} fragmentos adicionados ao ChromaDB.", flush=True)
        return True

    def vetorizar_texto(self, texto, source_name):
        """
        Vetoriza uma string já extraída (texto de documento aprovado ou correção RLHF).
        Evita re-processar o arquivo do disco quando o texto já está disponível.
        """
        if not texto or not texto.strip():
            return False
        from langchain_core.documents import Document
        doc = Document(page_content=texto, metadata={"source": source_name})
        return self._vetorizar_documentos([doc])

    @staticmethod
    def _normalizar_texto(texto):
        """Remove artefatos de extração de PDF já armazenados no banco."""
        if not texto:
            return texto
        texto = unicodedata.normalize('NFKC', texto)
        texto = texto.replace('Ɵ', 'ti')  # ligadura "ti" mal mapeada em PDFs brasileiros
        return texto

    @staticmethod
    def _extrair_trecho_relevante(texto, palavras_query, max_chars=8000):
        """Extrai o trecho do texto mais próximo das palavras da query."""
        if not texto:
            return ''
        texto_l = texto.lower()
        melhor_pos = len(texto)
        for p in palavras_query:
            idx = texto_l.find(p.lower())
            if 0 <= idx < melhor_pos:
                melhor_pos = idx
        # Centraliza o trecho: pega um pouco antes da palavra-chave e muito depois (tabela)
        inicio = max(0, melhor_pos - 400)
        fim = min(len(texto), inicio + max_chars)
        trecho = texto[inicio:fim].strip()
        if inicio > 0:
            trecho = '…' + trecho
        if fim < len(texto):
            trecho += '…'
        return trecho

    def buscar_documentos(self, query, k=6, user=None):
        """
        Busca Híbrida Universal — retorna lista de blocos de contexto (para Self-Audit).
        - Layer 1: Semântica (ChromaDB) — captura conceito e contexto.
        - Layer 2: Palavras-chave (DB) — RLHF, Ideias e Documentos da Biblioteca.
          O Layer 2 serve de fallback para documentos ainda não vetorizados no ChromaDB.
        """
        contexto_final = []
        has_db_hits = False
        fontes_vetoriais = set()  # evita duplicatas entre Layer 1 e Layer 2

        # --- PRÉ-PROCESSAMENTO ---
        # Mantemos uma versão da query que preserva melhor nomes de arquivos para a busca por keyword
        query_para_nome = query.lower().replace('(', ' ').replace(')', ' ').replace('[', ' ').replace(']', ' ')
        query_limpa = re.sub(r'[.,?!:;()\[\]"\']', ' ', query.lower())
        from .vocabulario import TERMOS_CONTABEIS, STOPWORDS_RAG

        palavras_query = [p for p in query_limpa.split() if p not in STOPWORDS_RAG and len(p) > 2]
        # Palavras para busca em nome de arquivo (podem ser mais curtas e específicas)
        palavras_nome = [p for p in query_para_nome.split() if len(p) > 2]

        termos_tecnicos = []
        for t in TERMOS_CONTABEIS:
            t_limpo = t.strip().lower()
            if re.search(r'\b' + re.escape(t_limpo) + r'\b', query_limpa):
                termos_tecnicos.append(t_limpo)

        def calcular_relevancia(texto, fonte=''):
            texto_l = (texto + ' ' + fonte).lower()
            score = 0
            # Peso para termos técnicos (Contabilidade)
            for t in termos_tecnicos:
                if t in texto_l: score += 2
            # Peso para palavras da query
            for p in palavras_query:
                if p in texto_l: score += 1
            # Bônus agressivo se a palavra da query estiver no nome do arquivo
            fonte_l = fonte.lower()
            for p in palavras_nome:
                if p in fonte_l: score += 4
            return score

        # --- LAYER 1: Busca Semântica (ChromaDB) ---
        try:
            # Recupera com scores (se disponível na versão da lib) ou usa busca padrão
            docs_vetoriais = self.vector_store.similarity_search(query, k=k)
            for doc in docs_vetoriais:
                fonte = doc.metadata.get('source', 'Documento Interno')
                fontes_vetoriais.add(fonte)

                score = calcular_relevancia(doc.page_content, fonte)

                # Se for planilha, aumentamos drasticamente a relevância e o tamanho do bloco
                conteudo_normalizado = self._normalizar_texto(doc.page_content)
                if fonte.lower().endswith(('.xls', '.xlsx')):
                    score += 5
                    bloco_texto = f"DOCUMENTO EXCEL INTEGRAL ({fonte}):\n{conteudo_normalizado}"
                else:
                    bloco_texto = f"DOCUMENTO APROVADO ({fonte}):\n{conteudo_normalizado}"

                # THRESHOLD DE SEGURANÇA (Rigor Contábil):
                if score >= 5:
                    contexto_final.append(bloco_texto)
                else:
                    print(f"[RAG] Documento {fonte} descartado por baixa relevância (Score: {score}).", flush=True)
        except Exception as e:
            print(f"[RAG Chroma] Erro: {e}", flush=True)

        # --- LAYER 2: Keyword Search (RLHF, Ideias e Biblioteca) ---
        try:
            from core.models import DocumentoBiblioteca, GlobalIdeia
            from .models import AIConsistencyCorrection
            from django.db.models import Q

            if palavras_query:
                # --- Via Expressa por Nome de Arquivo (todos os tipos) ---
                # Quando o usuário cita palavras que batem com o nome de um arquivo aprovado,
                # esse arquivo tem prioridade máxima sobre a busca semântica.
                # Evita colisão semântica (RAG entrega o arquivo errado) e alucinação por
                # âncora de domínio (modelo inventa conteúdo baseado no nome do arquivo).
                # XLS/XLSX → conteúdo integral; outros → trecho relevante (janela de 8000 chars).
                melhor_doc = None
                melhor_score_nome = 0
                for doc_candidato in DocumentoBiblioteca.objects.filter(status='approved'):
                    if doc_candidato.nome_arquivo in fontes_vetoriais:
                        continue
                    nome_limpo = doc_candidato.nome_arquivo.lower()
                    matches = [p for p in palavras_query if p in nome_limpo and len(p) > 3]
                    score_nome = len(matches) * 2 + sum(
                        1 for p in palavras_query if len(p) > 8 and p in nome_limpo
                    )
                    hit_forte = (
                        len(matches) >= 2
                        or any(p in nome_limpo for p in palavras_query if len(p) > 8)
                    )
                    if hit_forte and score_nome > melhor_score_nome:
                        melhor_score_nome = score_nome
                        melhor_doc = doc_candidato

                if melhor_doc:
                    ext_doc = melhor_doc.extensao.lower()
                    conteudo_doc = self._normalizar_texto(melhor_doc.conteudo_extraido or '')
                    fontes_vetoriais.add(melhor_doc.nome_arquivo)
                    has_db_hits = True
                    if ext_doc in ('xls', 'xlsx'):
                        # Excel → label específico: Modo Terminal (tabelas + abas)
                        contexto_final.append(
                            f"ARQUIVO EXCEL INTEGRAL DA CURADORIA ({melhor_doc.nome_arquivo}):\n"
                            f"{conteudo_doc}"
                        )
                    elif len(conteudo_doc) > 4000:
                        # Documento longo não-Excel (PDF, DOCX, etc.) → label próprio: Modo Transcrição
                        contexto_final.append(
                            f"DOCUMENTO INTEGRAL DA CURADORIA ({melhor_doc.nome_arquivo}):\n"
                            f"{conteudo_doc}"
                        )
                    else:
                        trecho = self._extrair_trecho_relevante(conteudo_doc, palavras_query)
                        if trecho:
                            contexto_final.append(
                                f"DOCUMENTO APROVADO ({melhor_doc.nome_arquivo}):\n{trecho}"
                            )
                    print(
                        f"[RAG Via Expressa] '{melhor_doc.nome_arquivo}' "
                        f"(score_nome={melhor_score_nome}, chars={len(conteudo_doc)})",
                        flush=True
                    )

                # RLHF (Correções de Curadoria)
                q_rlhf = Q()
                for p in palavras_query[:3]:
                    q_rlhf |= Q(user_query__icontains=p) | Q(titulo_melhoria__icontains=p)
                for cor in AIConsistencyCorrection.objects.filter(q_rlhf)[:2]:
                    contexto_final.append(
                        f"INSTRUÇÃO DE CURADORIA APROVADA ({cor.titulo_melhoria or 'RLHF'}):\n"
                        f"Pergunta do Usuário: {cor.user_query}\n"
                        f"Resposta Ideal (Siga este padrão): {cor.suggested_improvement}"
                    )
                    has_db_hits = True

                # Banco de Ideias
                q_ideias = Q()
                for p in palavras_query[:3]:
                    q_ideias |= Q(titulo__icontains=p) | Q(conteudo__icontains=p)
                for ideia in GlobalIdeia.objects.filter(ativa=True).filter(q_ideias)[:2]:
                    contexto_final.append(f"IDEIA REGISTRADA (Tema: {ideia.titulo}):\n{ideia.conteudo}")
                    has_db_hits = True

                # Biblioteca de Documentos — fallback para docs não vetorizados no ChromaDB
                q_bib = Q()
                for p in palavras_query[:4]:
                    q_bib |= Q(nome_arquivo__icontains=p) | Q(conteudo_extraido__icontains=p)
                docs_bib = (
                    DocumentoBiblioteca.objects
                    .filter(Q(status='approved') & q_bib)
                    .exclude(nome_arquivo__in=fontes_vetoriais)[:2]
                )
                for doc_bib in docs_bib:
                    trecho = self._extrair_trecho_relevante(
                        self._normalizar_texto(doc_bib.conteudo_extraido or ''), palavras_query
                    )
                    if trecho:
                        contexto_final.append(
                            f"DOCUMENTO APROVADO ({doc_bib.nome_arquivo}):\n{trecho}"
                        )
                        has_db_hits = True

        except Exception as e:
            print(f"[RAG DB] Erro: {e}", flush=True)

        return contexto_final, has_db_hits

    def buscar_conhecimento(self, query, k=6, user=None):
        """Wrapper de compatibilidade — retorna string formatada."""
        blocos, has_hits = self.buscar_documentos(query, k, user)
        return "\n\n---\n\n".join(blocos), has_hits
