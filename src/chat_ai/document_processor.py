import os
import datetime
import io
import tempfile
import contextlib
import sys
from PIL import Image

# Motor de extração de alta fidelidade
try:
    from docling.document_converter import DocumentConverter
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    print("[ALERTA] Docling não instalado. Usando motores legados.")

print("\n" + "#"*60)
print(f"DEBUG: MOTOR UNIVERSAL DOCLING CARREGADO EM: {datetime.datetime.now()}")
print("#"*60 + "\n")

class AnagmaDocumentProcessor:
    """
    Motor de extração Universal de alta fidelidade para a Anagma IA.
    Utiliza IBM Docling como motor principal para PDF, DOCX e XLSX.
    Mantém fallbacks para formatos legados e imagens.
    """

    MAX_PAGES = 10
    _ocr_reader = None
    _doc_converter = None

    @classmethod
    def _get_doc_converter(cls):
        """Inicializa o conversor Docling (Lazy Loading)"""
        if cls._doc_converter is None and DOCLING_AVAILABLE:
            try:
                # O Docling baixará os modelos na primeira execução se não estiverem no cache
                cls._doc_converter = DocumentConverter()
                print("[DOCLING] Motor de alta fidelidade inicializado.")
            except Exception as e:
                print(f"[DOCLING] Erro ao inicializar: {e}")
        return cls._doc_converter

    @classmethod
    def _get_ocr_reader(cls):
        """Inicializa o EasyOCR para imagens puras"""
        if cls._ocr_reader is None:
            try:
                import easyocr
                cls._ocr_reader = easyocr.Reader(['pt', 'en'], gpu=False)
            except Exception as e:
                print(f"[OCR] Erro ao carregar EasyOCR: {e}")
                return None
        return cls._ocr_reader

    @staticmethod
    def extrair_texto(file_obj, extensao):
        """
        Ponto de entrada único para extração de texto.
        Retorna tupla: (texto_extraido, metadados)
        """
        ext = extensao.lower().replace('.', '').strip()
        print(f"[DEBUG] Extração Universal. Extensão: {ext}")
        
        meta = {
            'motor': 'desconhecido',
            'fallback': False,
            'sucesso': False,
            'aviso': None
        }

        try:
            # 1. Tenta Docling para formatos modernos (PDF, DOCX, XLSX, PPTX)
            if DOCLING_AVAILABLE and ext in ['pdf', 'docx', 'xlsx', 'pptx']:
                resultado = AnagmaDocumentProcessor._processar_via_docling(file_obj, ext)
                if resultado:
                    meta.update({'motor': 'docling', 'sucesso': True})
                    return resultado, meta
                
                # Docling falhou ou retornou vazio — reposiciona e cai nos fallbacks
                if hasattr(file_obj, 'seek'):
                    file_obj.seek(0)
                meta['fallback'] = True
                print(f"[FALLBACK] Docling vazio para .{ext} — usando extrator legado.", flush=True)

            # 2. Fallbacks para outros formatos (também alcançados se Docling falhou)
            meta['motor'] = 'legado'
            if ext in ['png', 'jpg', 'jpeg']:
                res = AnagmaDocumentProcessor._processar_imagem(file_obj)
                meta['sucesso'] = bool(res and not res.startswith('Erro'))
                return res, meta
            elif ext == 'doc':
                res = AnagmaDocumentProcessor._processar_doc_legado(file_obj)
                meta['sucesso'] = bool(res and not res.startswith('Erro'))
                return res, meta
            elif ext == 'xls':
                res = AnagmaDocumentProcessor._processar_excel_legado(file_obj)
                meta['sucesso'] = bool(res and not res.startswith('Erro'))
                return res, meta
            elif ext == 'txt':
                res = AnagmaDocumentProcessor._processar_txt(file_obj)
                meta['sucesso'] = True
                return res, meta

            # 3. Fallbacks legados para PDF / DOCX / XLSX quando Docling não extraiu
            res = ""
            if ext == 'pdf': res = AnagmaDocumentProcessor._processar_pdf_legacy(file_obj)
            elif ext == 'docx': res = AnagmaDocumentProcessor._processar_docx_legacy(file_obj)
            elif ext == 'xlsx': res = AnagmaDocumentProcessor._processar_excel_legacy(file_obj, 'xlsx')

            if res:
                meta['sucesso'] = True
                return res, meta

            print(f"[DEBUG] Alerta: Extensão '{ext}' não possui processador.")
            return "", meta
        except Exception as e:
            print(f"[DEBUG] Erro crítico na extração: {e}")
            meta['sucesso'] = False
            return f"Erro ao processar arquivo: {str(e)}", meta

    @staticmethod
    def _processar_via_docling(file_obj, ext):
        """Extração de alta fidelidade usando Docling."""
        print(f"[DOCLING] Processando {ext}...")
        converter = AnagmaDocumentProcessor._get_doc_converter()
        if not converter:
            # Fallback automático se o Docling falhar na inicialização
            if ext == 'pdf': return AnagmaDocumentProcessor._processar_pdf_legacy(file_obj)
            if ext == 'docx': return AnagmaDocumentProcessor._processar_docx_legacy(file_obj)
            return ""

        try:
            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)
            
            # Salvamos em arquivo temporário pois o Docling prefere caminhos de disco
            with tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False) as tmp:
                tmp.write(file_obj.read())
                tmp_path = tmp.name

            try:
                # Silenciamos o Docling para evitar tracebacks técnicos no console do usuário
                with open(os.devnull, 'w') as fnull:
                    with contextlib.redirect_stderr(fnull), contextlib.redirect_stdout(fnull):
                        result = converter.convert(tmp_path, max_num_pages=AnagmaDocumentProcessor.MAX_PAGES)
                        markdown = result.document.export_to_markdown()
                
                print(f"[DOCLING] Sucesso. Tamanho: {len(markdown)} chars.")
                return markdown
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        except Exception:
            # Erro capturado silenciosamente para ativar o fallback sem sujar o console
            return ""

    @staticmethod
    def _processar_doc_legado(file_obj):
        """Mantido para compatibilidade com arquivos .doc antigos."""
        try:
            import win32com.client
            if hasattr(file_obj, 'seek'): file_obj.seek(0)
            content = file_obj.read()
            with tempfile.NamedTemporaryFile(suffix='.doc', delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                word = win32com.client.Dispatch("Word.Application")
                word.Visible = False
                word_doc = word.Documents.Open(os.path.abspath(tmp_path))
                texto = word_doc.Range().Text
                word_doc.Close(False)
                word.Quit()
                return texto
            finally:
                if os.path.exists(tmp_path): os.unlink(tmp_path)
        except:
            return "Erro ao processar .doc legado. Converta para .docx."

    @staticmethod
    def _detectar_linha_cabecalho(raw):
        """
        Detecta a primeira linha que parece ser um cabeçalho real:
        - Deve ter pelo menos metade das colunas preenchidas (evita linhas de título merged).
        - A maioria dos valores preenchidos deve ser string (não numérico).
        """
        import pandas as pd
        n_cols = len(raw.columns)
        min_cols = max(2, n_cols // 2)

        for i in range(min(15, len(raw))):
            row = raw.iloc[i]
            vals = [v for v in row if pd.notna(v) and str(v).strip() not in ('', 'nan')]
            if len(vals) < min_cols:
                continue  # linha esparsa (título merged ou linha vazia)
            strings = [v for v in vals if isinstance(v, str) and str(v).strip()]
            if strings and len(strings) / len(vals) >= 0.5:
                return i
        return 0

    @staticmethod
    def _limpar_dataframe(df):
        """Remove linhas completamente vazias, formata datas e substitui NaN por string vazia."""
        import pandas as pd
        df = df.dropna(how='all')
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime('%d/%m/%Y')
        return df.fillna('')

    @staticmethod
    def _df_para_markdown(raw, sheet_name):
        """
        Converte um DataFrame bruto (lido com header=None) em bloco markdown com cabeçalho
        auto-detectado, NaN limpos e datas formatadas.
        """
        import pandas as pd
        raw = raw.reset_index(drop=True)
        h = AnagmaDocumentProcessor._detectar_linha_cabecalho(raw)
        headers = [
            str(v).strip() if pd.notna(v) and str(v).strip() not in ('', 'nan') else f'Col_{i}'
            for i, v in enumerate(raw.iloc[h])
        ]
        df = raw.iloc[h + 1:].copy()
        df.columns = headers
        df = AnagmaDocumentProcessor._limpar_dataframe(df)
        if df.empty:
            return f"## Aba: {sheet_name}\n_(sem dados)_"
        return f"## Aba: {sheet_name}\n{df.to_markdown(index=False)}"

    @staticmethod
    def _processar_excel_legado(file_obj):
        """Tratamento para .xls (Excel 97-2003) com cabeçalho auto-detectado e sem nan."""
        try:
            import pandas as pd
            if hasattr(file_obj, 'seek'): file_obj.seek(0)
            raw_dict = pd.read_excel(
                io.BytesIO(file_obj.read()), sheet_name=None,
                engine='xlrd', header=None
            )
            res = [
                AnagmaDocumentProcessor._df_para_markdown(raw, name)
                for name, raw in raw_dict.items()
            ]
            return "\n\n".join(res)
        except Exception as e:
            return f"Erro ao processar .xls: {e}"

    @staticmethod
    def _processar_imagem(file_obj):
        try:
            if hasattr(file_obj, 'seek'): file_obj.seek(0)
            img_bytes = file_obj.read()
            reader = AnagmaDocumentProcessor._get_ocr_reader()
            if reader:
                return " ".join(reader.readtext(img_bytes, detail=0)).strip()
            return "OCR indisponível."
        except Exception as e:
            return f"Erro na imagem: {e}"

    @staticmethod
    def _processar_txt(file_obj):
        try:
            if hasattr(file_obj, 'seek'): file_obj.seek(0)
            content = file_obj.read()
            return content.decode('utf-8', errors='ignore') if isinstance(content, bytes) else content
        except:
            return ""

    # --- FALLBACKS LEGACY (Apenas se Docling falhar) ---

    @staticmethod
    def _processar_pdf_legacy(file_obj):
        import fitz
        try:
            if hasattr(file_obj, 'seek'): file_obj.seek(0)
            doc = fitz.open(stream=file_obj.read(), filetype="pdf")
            texto = ""
            for i in range(min(len(doc), 10)):
                texto += f"## Página {i+1}\n\n" + doc.load_page(i).get_text() + "\n\n"
            doc.close()
            return texto
        except: return ""

    @staticmethod
    def _processar_docx_legacy(file_obj):
        import docx
        try:
            if hasattr(file_obj, 'seek'): file_obj.seek(0)
            doc = docx.Document(io.BytesIO(file_obj.read()))
            return "\n".join([p.text for p in doc.paragraphs])
        except: return ""

    @staticmethod
    def _processar_excel_legacy(file_obj, ext):
        """Fallback legado para XLSX quando Docling falha — cabeçalho auto-detectado e sem nan."""
        import pandas as pd
        try:
            if hasattr(file_obj, 'seek'): file_obj.seek(0)
            raw_dict = pd.read_excel(io.BytesIO(file_obj.read()), sheet_name=None, header=None)
            res = [
                AnagmaDocumentProcessor._df_para_markdown(raw, name)
                for name, raw in raw_dict.items()
            ]
            return "\n\n".join(res)
        except Exception:
            return ""
