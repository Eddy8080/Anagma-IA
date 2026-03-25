# -*- coding: utf-8 -*-
import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

def finalizar_download():
    model_id = 'microsoft/Phi-3-mini-4k-instruct'
    target_dir = os.path.join('assets', 'models', 'phi-3-mini')
    
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
    
    print(f'Finalizando configuração do modelo de: {model_id}...')
    
    try:
        # Carrega do CACHE (não vai baixar os 7GB de novo)
        print('Carregando do cache interno...')
        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_id, 
            trust_remote_code=True,
            torch_dtype=torch.float16, # Definindo tipo explicitamente para evitar erro 'type'
            low_cpu_mem_usage=True
        )
        
        print('Salvando em diretório local...')
        tokenizer.save_pretrained(target_dir)
        model.save_pretrained(target_dir, safe_serialization=True)
        
        print('\n[SUCESSO] O cérebro da Anagma IA foi configurado com sucesso!')
        print(f'Local: {os.path.abspath(target_dir)}')
    except Exception as e:
        print(f'\n[ERRO] Falha na finalização: {str(e)}')

if __name__ == '__main__':
    finalizar_download()
