import os
import re
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
            chunk_size=1000,
            chunk_overlap=150,
            separators=["\n\n", "\n", " ", ""]
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

    def buscar_conhecimento(self, query, k=3, user=None):
        """
        Busca Híbrida Universal:
        - Layer 1: Busca Semântica (ChromaDB) - Captura o conceito/contexto.
        - Layer 2: Busca por Atributos (DB/Palavras) - Garante precisão em termos técnicos.
        """
        contexto_final = []
        has_db_hits = False

        # --- PRÉ-PROCESSAMENTO: Identificação de Intenção ---
        query_limpa = re.sub(r'[.,?!:;()\[\]"\']', ' ', query.lower())
        from .vocabulario import TERMOS_CONTABEIS, STOPWORDS_RAG
        
        # Identifica se a pergunta foca em termos técnicos específicos da nossa base
        palavras_query = [p for p in query_limpa.split() if p not in STOPWORDS_RAG and len(p) > 2]
        
        # Detecção robusta com bordas de palavra (\b)
        termos_tecnicos_encontrados = []
        for t in TERMOS_CONTABEIS:
            t_limpo = t.strip().lower()
            if re.search(r'\b' + re.escape(t_limpo) + r'\b', query_limpa):
                termos_tecnicos_encontrados.append(t_limpo)
        
        def calcular_relevancia_tecnica(texto):
            """Calcula o quanto o texto foca nos termos da pergunta."""
            texto_l = texto.lower()
            matches = sum(1 for t in termos_tecnicos_encontrados if t in texto_l)
            matches += sum(1 for p in palavras_query if p in texto_l)
            return matches

        # --- LAYER 1: Busca Semântica (O "Cérebro" Vetorial) ---
        try:
            # Buscamos por proximidade de conceito, sem thresholds matemáticos rígidos
            docs_vetoriais = self.vector_store.similarity_search(query, k=k)
            
            for doc in docs_vetoriais:
                # Se o documento vetorial tiver pelo menos um termo técnico ou palavra da query, 
                # ele é considerado um "hit" de alta relevância (Biblioteca).
                if calcular_relevancia_tecnica(doc.page_content) > 0:
                    fonte = doc.metadata.get('source', 'Documento Interno')
                    contexto_final.append(f"CONHECIMENTO OFICIAL (Fonte: {fonte}):\n{doc.page_content}")
                    has_db_hits = True
                else:
                    # Se for apenas semanticamente próximo, entra como contexto de apoio
                    contexto_final.append(f"CONTEXTO DE APOIO (Conceitos Relacionados):\n{doc.page_content}")
        except Exception as e:
            print(f"[RAG Chroma] Erro: {e}", flush=True)

        # --- LAYER 2: Keyword Search (RLHF e Ideias) ---
        try:
            from core.models import DocumentoBiblioteca, GlobalIdeia
            from .models import AIConsistencyCorrection
            from django.db.models import Q

            # Busca no DB por palavras-chave para complementar o vetor
            if palavras_query:
                q_filter = Q()
                for p in palavras_query[:3]:
                    q_filter |= Q(user_query__icontains=p) | Q(titulo_melhoria__icontains=p)
                
                # RLHF (Correções de Curadoria)
                correcoes = AIConsistencyCorrection.objects.filter(q_filter)[:2]
                for cor in correcoes:
                    contexto_final.append(
                        f"REGRA DE CURADORIA (Instrução Aprovada):\n"
                        f"Pergunta: {cor.user_query}\n"
                        f"Resposta a seguir: {cor.suggested_improvement}"
                    )
                    has_db_hits = True

                # Banco de Ideias
                q_ideias = Q(ativa=True)
                sub_ideias = Q()
                for p in palavras_query[:3]:
                    sub_ideias |= Q(titulo__icontains=p) | Q(conteudo__icontains=p)
                
                ideias = GlobalIdeia.objects.filter(q_ideias & sub_ideias)[:2]
                for ideia in ideias:
                    contexto_final.append(f"IDEIA REGISTRADA (Tema: {ideia.titulo}):\n{ideia.conteudo}")
                    has_db_hits = True

        except Exception as e:
            print(f"[RAG DB] Erro: {e}", flush=True)

        return "\n\n---\n\n".join(contexto_final), has_db_hits

        has_db_hits = chroma_contributed or keyword_contributed
        return "\n\n=== CONTEXTO ADICIONAL ===\n\n".join(contexto_final), has_db_hits
