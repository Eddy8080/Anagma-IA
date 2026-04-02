import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import os

class AnagmaDocumentProcessor:
    """
    Motor de extração de texto e OCR para a Anagma IA.
    Suporta PDF, PNG, JPG com limite de 10 páginas.
    """

    MAX_PAGES = 10

    @staticmethod
    def extrair_texto(file_obj, extensao):
        """
        Detecta o tipo de arquivo e extrai o texto.
        """
        ext = extensao.lower().replace('.', '')
        
        if ext == 'pdf':
            return AnagmaDocumentProcessor._processar_pdf(file_obj)
        elif ext in ['png', 'jpg', 'jpeg']:
            return AnagmaDocumentProcessor._processar_imagem(file_obj)
        return ""

    @staticmethod
    def _processar_pdf(file_obj):
        texto_final = []
        try:
            # Garante que o ponteiro está no início se for um arquivo aberto
            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)
            
            # Abre o PDF da memória
            doc = fitz.open(stream=file_obj.read(), filetype="pdf")
            num_paginas = min(len(doc), AnagmaDocumentProcessor.MAX_PAGES)

            for i in range(num_paginas):
                page = doc.load_page(i)
                texto = page.get_text().strip()
                
                # Se não houver texto nativo, tenta OCR na página
                if not texto:
                    pix = page.get_pixmap()
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    texto = pytesseract.image_to_string(img, lang='por')
                
                if texto:
                    texto_final.append(f"--- PÁGINA {i+1} ---\n{texto}")

            doc.close()
        except Exception as e:
            print(f"[ERRO OCR PDF] {e}")
            return f"Erro ao processar PDF: {str(e)}"

        return "\n\n".join(texto_final)

    @staticmethod
    def _processar_imagem(file_obj):
        try:
            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)
            img = Image.open(file_obj)
            texto = pytesseract.image_to_string(img, lang='por')
            return texto.strip()
        except Exception as e:
            print(f"[ERRO OCR IMAGEM] {e}")
            return f"Erro ao processar imagem: {str(e)}"
