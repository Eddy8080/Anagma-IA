# -*- coding: utf-8 -*-
import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

def download():
    model_id = 'microsoft/Phi-3-mini-4k-instruct'
    target_dir = os.path.join('assets', 'models', 'phi-3-mini')
    
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
    
    print(f'Iniciando download do modelo {model_id} para {target_dir}...')
    print('Isso pode levar alguns minutos dependendo da sua conexão...')
    
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_id, 
            trust_remote_code=True, 
            torch_dtype='auto', 
            device_map='auto'
        )
        
        tokenizer.save_pretrained(target_dir)
        model.save_pretrained(target_dir)
        print('\n[SUCESSO] Download e salvamento concluídos!')
        print(f'Modelo pronto em: {os.path.abspath(target_dir)}')
    except Exception as e:
        print(f'\n[ERRO] Falha ao baixar o modelo: {str(e)}')

if __name__ == '__main__':
    download()
