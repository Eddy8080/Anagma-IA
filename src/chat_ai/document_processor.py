import fitz  # PyMuPDF
from PIL import Image
import io
import os
import datetime

print("\n" + "#"*60)
print(f"DEBUG: MOTOR V3 CARREGADO EM: {datetime.datetime.now()}")
print("#"*60 + "\n")

class AnagmaDocumentProcessor:
    """
    Motor de extração de texto e OCR para a Anagma IA.
    Suporta PDF, DOCX, DOC, XLSX, XLS, TXT, PNG, JPG.
    """

    MAX_PAGES = 10
    _ocr_reader = None

    @classmethod
    def _get_ocr_reader(cls):
        """Inicializa o EasyOCR apenas quando necessário (lazy loading)"""
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
        Detecta o tipo de arquivo e extrai o texto com logs de depuração.
        """
        ext = extensao.lower().replace('.', '').strip()
        print(f"[DEBUG] Extraindo texto. Extensão detectada: {ext}")
        
        try:
            if ext == 'pdf':
                return AnagmaDocumentProcessor._processar_pdf(file_obj)
            elif ext in ['png', 'jpg', 'jpeg']:
                return AnagmaDocumentProcessor._processar_imagem(file_obj)
            elif ext == 'docx':
                return AnagmaDocumentProcessor._processar_docx(file_obj)
            elif ext == 'doc':
                return AnagmaDocumentProcessor._processar_doc_legado(file_obj)
            elif ext in ['xlsx', 'xls']:
                return AnagmaDocumentProcessor._processar_excel(file_obj, ext)
            elif ext == 'txt':
                return AnagmaDocumentProcessor._processar_txt(file_obj)
            
            print(f"[DEBUG] Alerta: Extensão '{ext}' não possui processador mapeado.")
            return ""
        except Exception as e:
            print(f"[DEBUG] Erro catastrófico no roteamento de extração: {e}")
            return f"Erro interno ao processar arquivo: {str(e)}"

    @staticmethod
    def _processar_doc_legado(file_obj):
        print(f"[DEBUG] Iniciando processamento de DOC legado...")
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
        content = file_obj.read()

        # Estratégia 1: win32com via Microsoft Word (Windows)
        try:
            import win32com.client
            import tempfile
            import os as _os
            with tempfile.NamedTemporaryFile(suffix='.doc', delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                word = win32com.client.Dispatch("Word.Application")
                word.Visible = False
                word_doc = word.Documents.Open(_os.path.abspath(tmp_path))
                texto = word_doc.Range().Text
                word_doc.Close(False)
                word.Quit()
                print(f"[DEBUG] DOC processado via Word COM. Tamanho: {len(texto)}")
                return texto
            finally:
                try:
                    _os.unlink(tmp_path)
                except Exception:
                    pass
        except ImportError:
            print("[DEBUG] win32com não disponível. Tentando unstructured...")
        except Exception as e_com:
            print(f"[DEBUG] win32com falhou: {e_com}. Tentando unstructured...")

        # Estratégia 2: unstructured (requer LibreOffice no sistema)
        try:
            from unstructured.partition.doc import partition_doc
            buffer = io.BytesIO(content)
            elements = partition_doc(file=buffer)
            texto = "\n\n".join([str(el) for el in elements if str(el).strip()])
            print(f"[DEBUG] DOC processado via unstructured. Tamanho: {len(texto)}")
            return texto
        except Exception as e:
            print(f"[DEBUG] Erro no DOC legado (unstructured): {e}")
            return (
                f"Não foi possível extrair texto do arquivo .doc: {str(e)}. "
                "Instale o Microsoft Word ou o LibreOffice, ou converta o arquivo para .docx antes de subir."
            )

    @staticmethod
    def _processar_docx(file_obj):
        print(f"[DEBUG] Iniciando processamento de DOCX...")
        try:
            import docx as python_docx
            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)

            content = file_obj.read()
            if not content:
                print("[DEBUG] Erro: Arquivo DOCX vazio.")
                return "Erro: O arquivo DOCX parece estar vazio."

            buffer = io.BytesIO(content)
            try:
                doc = python_docx.Document(buffer)
            except Exception as zip_err:
                # Arquivo pode ser um .doc binário renomeado para .docx
                print(f"[DEBUG] DOCX falhou como ZIP (possível .doc binário): {zip_err}")
                return AnagmaDocumentProcessor._processar_doc_legado(io.BytesIO(content))

            # Parágrafos normais
            partes = [para.text for para in doc.paragraphs if para.text.strip()]

            # Tabelas em formato markdown completo (cabeçalho + separador + dados)
            for table in doc.tables:
                linhas = []
                for row in table.rows:
                    celulas = [cell.text.strip().replace('\n', ' ') for cell in row.cells]
                    linhas.append(celulas)
                if not linhas:
                    continue
                n_cols = max(len(r) for r in linhas)
                # Normaliza colunas
                linhas = [r + [''] * (n_cols - len(r)) for r in linhas]
                md_header = '| ' + ' | '.join(linhas[0]) + ' |'
                md_sep    = '| ' + ' | '.join(['---'] * n_cols) + ' |'
                md_rows   = ['| ' + ' | '.join(r) + ' |' for r in linhas[1:]]
                partes.append('\n'.join([md_header, md_sep] + md_rows))

            texto = "\n".join(partes)
            print(f"[DEBUG] DOCX processado. Tamanho do texto: {len(texto)}")
            return texto
        except Exception as e:
            print(f"[DEBUG] Erro no DOCX: {e}")
            return f"Erro ao processar DOCX: {str(e)}"

    @staticmethod
    def _processar_excel(file_obj, ext):
        print(f"[DEBUG] Iniciando processamento de EXCEL ({ext})...")
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
        content = file_obj.read()
        buffer = io.BytesIO(content)

        # Estratégia 1: pandas (mais completo, preserva tipos e formatação)
        try:
            import pandas as pd
            engine = 'openpyxl' if ext == 'xlsx' else 'xlrd'
            print(f"[DEBUG] Usando motor pandas: {engine}")
            df_dict = pd.read_excel(buffer, sheet_name=None, engine=engine)
            texto_final = []
            for sheet_name, df in df_dict.items():
                texto_final.append(f"## Aba: {sheet_name}\n")
                try:
                    texto_final.append(df.to_markdown(index=False))
                except Exception:
                    texto_final.append(df.to_string(index=False))
            texto = "\n\n".join(texto_final)
            print(f"[DEBUG] EXCEL processado via pandas. Tamanho: {len(texto)}")
            return texto
        except Exception as e_pd:
            print(f"[DEBUG] pandas falhou ({e_pd}). Tentando openpyxl direto...")

        # Estratégia 2: openpyxl direto (apenas xlsx)
        if ext == 'xlsx':
            try:
                from openpyxl import load_workbook
                buffer.seek(0)
                wb = load_workbook(buffer, read_only=True, data_only=True)
                texto_final = []
                for sheet_name in wb.sheetnames:
                    ws = wb[sheet_name]
                    texto_final.append(f"--- ABA: {sheet_name} ---")
                    for row in ws.iter_rows(values_only=True):
                        linha = "\t".join([str(v) if v is not None else "" for v in row])
                        if linha.strip():
                            texto_final.append(linha)
                wb.close()
                texto = "\n".join(texto_final)
                print(f"[DEBUG] XLSX processado via openpyxl direto. Tamanho: {len(texto)}")
                return texto
            except Exception as e_opx:
                print(f"[DEBUG] openpyxl direto falhou: {e_opx}")
                return f"Erro ao processar XLSX: {str(e_opx)}"

        # Estratégia 3: win32com via Microsoft Excel (apenas xls, Windows)
        try:
            import win32com.client
            import tempfile
            import os as _os
            buffer.seek(0)
            with tempfile.NamedTemporaryFile(suffix='.xls', delete=False) as tmp:
                tmp.write(buffer.read())
                tmp_path = tmp.name
            try:
                excel = win32com.client.Dispatch("Excel.Application")
                excel.Visible = False
                excel.DisplayAlerts = False
                wb = excel.Workbooks.Open(_os.path.abspath(tmp_path))
                texto_final = []
                for sheet in wb.Worksheets:
                    texto_final.append(f"--- ABA: {sheet.Name} ---")
                    used = sheet.UsedRange
                    for row in used.Rows:
                        celulas = []
                        for cell in row.Columns:
                            v = cell.Value
                            if v is not None:
                                celulas.append(str(v))
                        if any(c.strip() for c in celulas):
                            texto_final.append("\t".join(celulas))
                wb.Close(False)
                excel.Quit()
                texto = "\n".join(texto_final)
                print(f"[DEBUG] XLS processado via Excel COM. Tamanho: {len(texto)}")
                return texto
            finally:
                try:
                    _os.unlink(tmp_path)
                except Exception:
                    pass
        except ImportError:
            pass
        except Exception as e_com:
            print(f"[DEBUG] Excel COM falhou: {e_com}")

        return "Erro ao processar XLS: instale o Microsoft Excel ou converta para .xlsx antes de subir."

    @staticmethod
    def _processar_txt(file_obj):
        try:
            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)
            content = file_obj.read()
            if isinstance(content, bytes):
                return content.decode('utf-8', errors='ignore')
            return content
        except Exception as e:
            return f"Erro ao processar TXT: {str(e)}"

    @staticmethod
    def _processar_pdf(file_obj):
        print(f"[DEBUG] Iniciando processamento de PDF...")
        texto_final = []
        try:
            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)

            content = file_obj.read()

            if not content:
                print("[DEBUG] Erro no PDF: arquivo vazio (0 bytes lidos).")
                return "Erro: O arquivo PDF está vazio ou não foi enviado corretamente."

            print(f"[DEBUG] PDF recebido: {len(content)} bytes.")

            doc = fitz.open(stream=content, filetype="pdf")

            # Rejeita PDF com senha
            if doc.is_encrypted:
                doc.close()
                print("[DEBUG] Erro no PDF: arquivo protegido por senha.")
                return "Erro: O PDF está protegido por senha. Remova a proteção antes de enviar."

            num_paginas = min(len(doc), AnagmaDocumentProcessor.MAX_PAGES)
            print(f"[DEBUG] PDF aberto: {len(doc)} páginas totais, processando {num_paginas}.")

            for i in range(num_paginas):
                page = doc.load_page(i)

                # Modo markdown (tabelas detectadas geometricamente)
                # Alguns PDFs disparam AssertionError neste modo — fallback para texto simples
                texto = ""
                try:
                    texto = page.get_text("markdown").strip()
                except Exception:
                    pass

                if not texto:
                    try:
                        texto = page.get_text("text").strip()
                    except Exception:
                        pass

                if not texto:
                    # Fallback OCR para páginas escaneadas (sem texto extraível)
                    pix = page.get_pixmap()
                    img_bytes = pix.tobytes("png")
                    reader = AnagmaDocumentProcessor._get_ocr_reader()
                    if reader:
                        resultados = reader.readtext(img_bytes, detail=0)
                        texto = " ".join(resultados)

                if texto:
                    texto_final.append(f"## Página {i+1}\n\n{texto}")

            doc.close()
            final = "\n\n".join(texto_final)
            print(f"[DEBUG] PDF processado com sucesso. Tamanho: {len(final)} chars.")
            return final

        except Exception as e:
            tipo = type(e).__name__
            detalhe = repr(e)
            print(f"[DEBUG] Erro no PDF: tipo={tipo} | detalhe={detalhe}")

            # Fallback: tenta pdfplumber como segunda opção
            try:
                import pdfplumber
                if hasattr(file_obj, 'seek'):
                    file_obj.seek(0)
                content_fb = file_obj.read() if not content else content
                with pdfplumber.open(io.BytesIO(content_fb)) as pdf_fb:
                    paginas = []
                    for i, pg in enumerate(pdf_fb.pages[:AnagmaDocumentProcessor.MAX_PAGES]):
                        t = pg.extract_text() or ''
                        if t.strip():
                            paginas.append(f"## Página {i+1}\n\n{t.strip()}")
                    if paginas:
                        final_fb = "\n\n".join(paginas)
                        print(f"[DEBUG] PDF recuperado via pdfplumber. Tamanho: {len(final_fb)} chars.")
                        return final_fb
            except Exception as e_fb:
                print(f"[DEBUG] Fallback pdfplumber também falhou: {repr(e_fb)}")

            return f"Erro ao processar PDF ({tipo}): {detalhe}. Tente converter o arquivo ou remova proteções."

    @staticmethod
    def _processar_imagem(file_obj):
        try:
            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)
            
            img_bytes = file_obj.read()
            reader = AnagmaDocumentProcessor._get_ocr_reader()
            if reader:
                resultados = reader.readtext(img_bytes, detail=0)
                return " ".join(resultados).strip()
            return "Erro: Motor de OCR EasyOCR não disponível."
        except Exception as e:
            return f"Erro ao processar imagem: {str(e)}"
