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
        Busca semântica nos documentos vetorizados.
        Retorna string vazia se não houver documentos indexados.
        """
        try:
            results = self.vector_store.similarity_search(query, k=k)
            if not results:
                return ""
            return "\n---\n".join([doc.page_content for doc in results])
        except Exception as e:
            print(f"[RAG] Erro na busca: {e}")
            return ""
