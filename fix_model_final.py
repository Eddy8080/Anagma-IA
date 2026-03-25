# -*- coding: utf-8 -*-
import os
from huggingface_hub import snapshot_download

def fix_and_move():
    model_id = 'microsoft/Phi-3-mini-4k-instruct'
    target_dir = os.path.abspath(os.path.join('assets', 'models', 'phi-3-mini'))
    
    print(f'Sincronizando arquivos do cache para: {target_dir}...')
    
    try:
        # O snapshot_download detecta que os arquivos já estão no cache
        # e apenas os copia/linka para a pasta de destino sem carregar o modelo no Python
        snapshot_download(
            repo_id=model_id,
            local_dir=target_dir,
            local_dir_use_symlinks=False, # Importante para o Inno Setup/Windows
            library_name="transformers"
        )
        
        print('\n[SUCESSO ABSOLUTO] O cérebro da Anagma IA está no lugar certo!')
        print(f'Arquivos conferidos em: {target_dir}')
        
        # Lista os arquivos para confirmar
        files = os.listdir(target_dir)
        print(f'Total de arquivos movidos: {len(files)}')
        
    except Exception as e:
        print(f'\n[ERRO] Falha na sincronização: {str(e)}')

if __name__ == '__main__':
    fix_and_move()
