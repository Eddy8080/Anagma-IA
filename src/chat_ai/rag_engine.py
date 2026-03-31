import os
import pandas as pd
from langchain_community.document_loaders import UnstructuredFileLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
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
        Transforma documentos em vetores e salva no ChromaDB.
        """
        chunks = self.text_splitter.split_documents(docs)
        # Adiciona ao vector_store existente e atualiza a referência local
        self.vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory=self.persist_directory
        )
        print(f"Sucesso: {len(chunks)} fragmentos vetorizados.")
        return True

    def buscar_conhecimento(self, query, k=3):
        """
        Busca semântica nos documentos vetorizados (ChromaDB)
        E busca textual nos documentos aprovados na Biblioteca.
        """
        contexto_final = []

        # 1. Busca no ChromaDB (Documentos Fixos)
        try:
            results = self.vector_store.similarity_search(query, k=k)
            if results:
                contexto_final.append("\n---\n".join([doc.page_content for doc in results]))
        except Exception as e:
            print(f"[RAG Chroma] Erro: {e}")

        # 2. Busca na Biblioteca de Curadoria (Documentos Aprovados)
        try:
            from core.models import DocumentoBiblioteca, GlobalIdeia
            from django.db.models import Q
            
            # Busca simples por palavras-chave na query (melhor performance para banco)
            palavras = [p for p in query.split() if len(p) > 3]
            
            # --- BUSCA NA BIBLIOTECA ---
            # Primeiro, busca exata por nome de arquivo para informar status
            docs_status = DocumentoBiblioteca.objects.filter(nome_arquivo__icontains=query).only('nome_arquivo', 'status')[:3]
            for ds in docs_status:
                status_pt = dict(DocumentoBiblioteca.STATUS_CHOICES).get(ds.status, ds.status)
                contexto_final.append(f"INFO SISTEMA: O arquivo '{ds.nome_arquivo}' existe no sistema com o status: {status_pt}.")

            # Depois, busca conteúdo apenas dos aprovados
            query_bib = Q(status='approved')
            if palavras:
                sub_query = Q()
                for p in palavras[:5]:
                    sub_query |= Q(conteudo_extraido__icontains=p) | Q(nome_arquivo__icontains=p)
                query_bib &= sub_query

            docs_biblioteca = DocumentoBiblioteca.objects.filter(query_bib).only('conteudo_extraido', 'nome_arquivo')[:2]
            
            for doc in docs_biblioteca:
                contexto_final.append(f"DOCUMENTO APROVADO ({doc.nome_arquivo}):\n{doc.conteudo_extraido[:2000]}")

            # --- BUSCA NO BANCO DE IDEIAS (GlobalIdeia) ---
            query_ideias = Q(ativa=True)
            if palavras:
                sub_query_ideia = Q()
                for p in palavras[:5]:
                    sub_query_ideia |= Q(titulo__icontains=p) | Q(conteudo__icontains=p)
                query_ideias &= sub_query_ideia

            ideias = GlobalIdeia.objects.filter(query_ideias).only('titulo', 'conteudo')[:3]
            
            for ideia in ideias:
                contexto_final.append(f"IDEIA DO BANCO DE IDEIAS ({ideia.titulo}):\n{ideia.conteudo}")

        except Exception as e:
            print(f"[RAG Banco de Dados] Erro: {e}")

        return "\n\n=== CONTEXTO ADICIONAL ===\n\n".join(contexto_final)
