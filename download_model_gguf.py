# -*- coding: utf-8 -*-
"""
Script para baixar o modelo Phi-3-mini-4k-instruct em formato GGUF quantizado (Q4_K_M).
Tamanho: ~2.4 GB
Origem: microsoft/Phi-3-mini-4k-instruct-gguf (HuggingFace - oficial Microsoft)

Uso:
    python download_model_gguf.py
"""
import os
import sys
import urllib.request

DEST_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'models', 'phi-3-mini-gguf')
FILENAME = 'Phi-3-mini-4k-instruct-q4.gguf'
DEST_PATH = os.path.join(DEST_DIR, FILENAME)

# URL direta do HuggingFace (repositório oficial Microsoft)
HF_REPO = 'microsoft/Phi-3-mini-4k-instruct-gguf'
HF_URL = f'https://huggingface.co/{HF_REPO}/resolve/main/{FILENAME}'


def progresso(count, block_size, total_size):
    percent = int(count * block_size * 100 / total_size)
    baixado_mb = count * block_size / 1e6
    total_mb = total_size / 1e6
    print(f'\r  {percent}%  [{baixado_mb:.1f} MB / {total_mb:.1f} MB]', end='', flush=True)


def download():
    os.makedirs(DEST_DIR, exist_ok=True)

    if os.path.exists(DEST_PATH):
        tamanho_mb = os.path.getsize(DEST_PATH) / 1e6
        print(f'[OK] Modelo já existe: {DEST_PATH} ({tamanho_mb:.0f} MB)')
        return True

    print(f'[DOWNLOAD] Baixando {FILENAME}...')
    print(f'           Origem : {HF_URL}')
    print(f'           Destino: {DEST_PATH}')
    print(f'           Tamanho: ~2.4 GB — aguarde...\n')

    try:
        urllib.request.urlretrieve(HF_URL, DEST_PATH, reporthook=progresso)
        print()
        tamanho_mb = os.path.getsize(DEST_PATH) / 1e6
        print(f'\n[SUCESSO] Modelo salvo: {DEST_PATH} ({tamanho_mb:.0f} MB)')
        return True
    except Exception as e:
        print(f'\n[ERRO] Falha no download: {e}')
        if os.path.exists(DEST_PATH):
            os.remove(DEST_PATH)
        print('\nAlternativa manual:')
        print(f'  1. Acesse: https://huggingface.co/{HF_REPO}')
        print(f'  2. Baixe o arquivo: {FILENAME}')
        print(f'  3. Salve em: {DEST_DIR}')
        return False


if __name__ == '__main__':
    sucesso = download()
    sys.exit(0 if sucesso else 1)
