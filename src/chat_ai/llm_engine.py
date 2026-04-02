# -*- coding: utf-8 -*-
"""
Motor de Inferência da Anagma IA.
Backend primário : llama-cpp-python com Phi-3-mini GGUF Q4_K_M (~2.4 GB, CPU)
Backend fallback : transformers + safetensors float16 (~4.6 GB, CPU)
"""
import os
import traceback
import threading
from django.conf import settings
from .rag_engine import AnagmaRAGEngine
from .vocabulario import SAUDACOES, GATILHOS_SOBRE_IA, PARES_SOBRE_IA


class AnagmaLLMEngine:
    """Singleton que carrega o modelo uma única vez e o mantém em RAM."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.rag = AnagmaRAGEngine()
                cls._instance._backend = None
                cls._instance._llm = None
                cls._instance._pipe = None
                cls._instance._load_model()
        return cls._instance

    # ------------------------------------------------------------------
    # Carregamento
    # ------------------------------------------------------------------

    def _load_model(self):
        print('\n[SISTEMA] --- CARREGANDO CÉREBRO PERMANENTE ---', flush=True)

        gguf_path = os.path.abspath(getattr(settings, 'GGUF_MODEL_PATH', ''))
        safetensors_path = os.path.abspath(getattr(settings, 'MICROSOFT_MODEL_PATH', ''))

        if os.path.exists(gguf_path):
            self._carregar_gguf(gguf_path)
        elif os.path.exists(safetensors_path):
            print('[AVISO] Modelo GGUF não encontrado. Usando safetensors (mais lento).', flush=True)
            self._carregar_safetensors(safetensors_path)
        else:
            print('[ERRO] Nenhum modelo encontrado. Execute download_model_gguf.py.', flush=True)

    def _carregar_gguf(self, model_path):
        try:
            from llama_cpp import Llama
            import psutil

            ram_antes = psutil.virtual_memory().used / 1e9
            print(f'[SISTEMA] Carregando GGUF: {model_path}', flush=True)

            n_threads = max(1, os.cpu_count() // 2)

            self._llm = Llama(
                model_path=model_path,
                n_ctx=4096,
                n_threads=n_threads,
                n_gpu_layers=0,
                verbose=False,
            )
            self._backend = 'gguf'

            ram_depois = psutil.virtual_memory().used / 1e9
            print(f'[SISTEMA] RAM: +{ram_depois - ram_antes:.1f} GB | Threads: {n_threads}', flush=True)
            print('[SISTEMA] --- SUCESSO: ANAGMA IA ESTÁ PRONTA (GGUF) ---\n', flush=True)

        except ImportError:
            safetensors_path = os.path.abspath(getattr(settings, 'MICROSOFT_MODEL_PATH', ''))
            if os.path.exists(safetensors_path):
                self._carregar_safetensors(safetensors_path)
        except MemoryError:
            print('[ERRO CRÍTICO] RAM insuficiente para o modelo GGUF.', flush=True)
        except Exception as e:
            print(f'[ERRO CRÍTICO] Falha ao carregar GGUF: {e}', flush=True)
            traceback.print_exc()

    def _carregar_safetensors(self, model_path):
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline, AutoConfig

            config = AutoConfig.from_pretrained(model_path, trust_remote_code=False)
            config.use_cache = False

            self._tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=False)

            print('[SISTEMA] Alocando pesos safetensors em float16...', flush=True)
            self._model = AutoModelForCausalLM.from_pretrained(
                model_path, config=config, trust_remote_code=False,
                dtype=torch.float16, device_map='cpu',
                low_cpu_mem_usage=True, attn_implementation='eager',
            )
            self._pipe = pipeline('text-generation', model=self._model, tokenizer=self._tokenizer)
            self._backend = 'transformers'
            print('[SISTEMA] --- SUCESSO: ANAGMA IA ESTÁ PRONTA (safetensors) ---\n', flush=True)

        except MemoryError:
            print('[ERRO CRÍTICO] RAM insuficiente.', flush=True)
        except Exception as e:
            print(f'[ERRO CRÍTICO] Falha ao carregar safetensors: {e}', flush=True)
            traceback.print_exc()

    # ------------------------------------------------------------------
    # Geração de resposta
    # ------------------------------------------------------------------

    @property
    def pronto(self):
        return self._backend is not None

    def _contar_tokens_aprox(self, texto):
        """Estimativa conservadora: 1 token a cada 3 caracteres (PT-BR)."""
        if not texto:
            return 0
        return len(texto) // 3 + 1

    def _get_perfil_anagma(self):
        from django.core.cache import cache
        perfil = cache.get('perfil_anagma')
        if perfil is None:
            from core.models import PerfilAnagma
            perfil = PerfilAnagma.get().texto or ''
            cache.set('perfil_anagma', perfil, timeout=300)
        return perfil

    def _e_saudacao(self, texto):
        return texto.strip().lower().rstrip('!.,') in SAUDACOES

    def _e_pergunta_sobre_ia(self, texto):
        t = texto.strip().lower()
        if any(g in t for g in GATILHOS_SOBRE_IA):
            return True
        palavras = set(t.split())
        return any(a in palavras and b in palavras for a, b in PARES_SOBRE_IA)

    def gerar_resposta(self, user_query, chat_history=None, user_name=None, saudacao=None, search_query=None, user=None):
        """
        Gera resposta usando RAG + Phi-3 com gestão de contexto e thread-safety.
        """
        if not self.pronto:
            return 'Desculpe, o motor de IA não está disponível. Verifique os logs do servidor.'

        # Intercepta saudações simples — o modelo pequeno não segue instruções sobre isso
        if self._e_saudacao(user_query):
            import random
            nome = user_name or 'usuário'
            primeiro_nome = nome.split()[0] if nome else nome
            cumprimento = saudacao or 'Boa tarde'
            texto_limpo = user_query.strip().lower().rstrip('!.,')
            _informais = {'oi', 'olá', 'ola', 'hello', 'hi', 'hey', 'oi!', 'olá!'}
            informal = texto_limpo in _informais
            if informal:
                opcoes = [
                    f"Oi, {primeiro_nome}! Tudo bem? Como posso ajudar hoje?",
                    f"Olá, {primeiro_nome}! Pode perguntar, estou aqui para ajudar.",
                    f"Oi! Por aqui tudo certo, {primeiro_nome}. O que você precisa?",
                ]
            else:
                opcoes = [
                    f"{cumprimento}, {primeiro_nome}! Como posso ajudar você hoje?",
                    f"{cumprimento}, {primeiro_nome}! Pronta para ajudar. O que precisa?",
                    f"{cumprimento}, {primeiro_nome}! Em que posso ser útil?",
                ]
            return random.choice(opcoes)

        # Intercepta perguntas sobre a própria IA — o modelo pequeno tende a virar "manual"
        if self._e_pergunta_sobre_ia(user_query):
            import random
            primeiro_nome = (user_name or 'usuário').split()[0]
            opcoes = [
                (
                    f"Sou a **Anagma IA**, sua assistente de contabilidade e tributos brasileiros, {primeiro_nome}! "
                    f"Você pode me perguntar sobre IRPJ, CSLL, Simples Nacional, folha de pagamento, notas fiscais, "
                    f"SPED, eSocial — qualquer coisa da área contábil e fiscal. "
                    f"Também recebo documentos em PDF ou imagem direto no chat para analisar na hora. "
                    f"O que você quer resolver hoje?"
                ),
                (
                    f"Olha, {primeiro_nome}, sou especialista em contabilidade e tributação brasileira. "
                    f"Tiro dúvidas sobre impostos, regimes tributários, obrigações acessórias, folha de pagamento e muito mais. "
                    f"Se tiver um documento para analisar, é só anexar aqui no chat — leio PDF e imagem. "
                    f"Por onde quer começar?"
                ),
                (
                    f"Sou a Anagma IA! Funciono como um especialista contábil disponível aqui no sistema, {primeiro_nome}. "
                    f"Pode me mandar perguntas sobre tributos, escrituração, IRRF, CSLL, ICMS, ISS, folha — tudo da área. "
                    f"Também analiso documentos que você anexar. "
                    f"Tem alguma dúvida específica?"
                ),
            ]
            return random.choice(opcoes)

        # Usa search_query (contextualizada) para busca no RAG, mas responde ao user_query original
        contexto_rag = self.rag.buscar_conhecimento(search_query or user_query, user=user)
        perfil_anagma = self._get_perfil_anagma()

        # --- Monta o system prompt ---
        nome = user_name or 'usuário'
        cumprimento = saudacao or 'Boa tarde'

        _periodo_map = {'Bom dia': 'manhã', 'Boa tarde': 'tarde', 'Boa noite': 'noite'}
        periodo = _periodo_map.get(cumprimento, 'tarde')

        system_msg = f"""IDENTIDADE E MANDATO SUPREMO:
- Você é a **Anagma IA**, a inteligência artificial especialista e oficial da empresa **Anagma**.
- Sua comunicação deve ser em **Português Brasileiro de alto nível**, técnico, claro e sem erros gramaticais.
- Você opera em um ambiente **100% DIGITAL**. NÃO existem bibliotecas físicas, salas, atendentes humanos ou contatos externos. Toda a gestão de documentos é feita pelo sistema Anagma que o usuário está acessando agora.

SAUDAÇÃO OBRIGATÓRIA:
- Comece SEMPRE com: "{cumprimento}, {nome}!".

REGRAS DE RESPOSTA E AUTORIDADE:
1. **Prioridade de Dados:** Se a informação estiver no CONTEXTO INTERNO abaixo (Biblioteca ou Banco de Ideias), use-a como VERDADE ABSOLUTA. Se o status de um arquivo for "Aprovado", você JÁ POSSUI o conhecimento dele. NÃO diga que "está em auditoria" ou que "precisa confirmar". Responda diretamente com base no conteúdo disponível.
2. **Status de Documentos:** Se o status for "Pendente", informe que ele está em processamento. Se for "Aprovado", você deve ser a voz técnica que explica o que há no arquivo.
3. **Fim das Alucinações:** JAMAIS sugira contatos externos ou locais físicos. Toda a gestão é digital.
4. **Domínio:** Responda apenas sobre contabilidade, tributos e finanças brasileiras.
5. **Honestidade Intelectual:** Se não encontrar o dado no contexto e não tiver certeza, admita que não encontrou. NUNCA invente informações.
6. **Saudações:** Se o usuário enviar apenas uma saudação (ex: "Boa tarde", "Olá", "Bom dia", "Oi"), responda com a saudação, apresente-se brevemente como Anagma IA e pergunte em que pode ajudar. NUNCA explique o significado da saudação nem traduza para outros idiomas.

CONTEXTO DA EMPRESA:
{perfil_anagma if perfil_anagma else 'Empresa Anagma - Especialista em Contabilidade Digital.'}

"""

        if contexto_rag:
            system_msg += f'\n\nCONHECIMENTO TÉCNICO E DOCUMENTAL (BIBLIOTECA):\n{contexto_rag}'

        # --- GESTÃO DE CONTEXTO ---
        MAX_CONTEXT_TOKENS = 3500
        tokens_fixos = self._contar_tokens_aprox(system_msg) + self._contar_tokens_aprox(user_query)
        available_for_history = MAX_CONTEXT_TOKENS - tokens_fixos
        
        messages = [{'role': 'system', 'content': system_msg}]
        
        if chat_history:
            temp_history = []
            current_history_tokens = 0
            for msg in reversed(chat_history):
                if msg.get('role') in ('user', 'assistant') and msg.get('content'):
                    msg_tokens = self._contar_tokens_aprox(msg['content'])
                    if current_history_tokens + msg_tokens < available_for_history:
                        temp_history.insert(0, {'role': msg['role'], 'content': msg['content']})
                        current_history_tokens += msg_tokens
                    else:
                        break
            messages.extend(temp_history)

        messages.append({'role': 'user', 'content': user_query})

        if self._backend == 'gguf':
            res = self._gerar_gguf(messages)
        else:
            res = self._gerar_safetensors(messages)
            
        return self._limpar_resposta(res)

    def _limpar_resposta(self, texto):
        """Remove notas explicativas ou metadados que o modelo possa anexar por erro de instrução."""
        if not texto: return texto
        
        import re
        # Remove blocos como (Note: ...), (Observação: ...), [Note: ...], etc.
        padroes = [
            r'\(Note:.*?\)', r'\[Note:.*?\]', r'\(Observação:.*?\)', r'\[Observação:.*?\]',
            r'\nNote:.*$', r'\nObservação:.*$', r'^\s*Note:.*$', r'^\s*Observação:.*$'
        ]
        for p in padroes:
            texto = re.sub(p, '', texto, flags=re.IGNORECASE | re.DOTALL).strip()
            
        # Limpeza adicional de quebras de linha duplas no final
        return texto.strip()

    def _gerar_gguf(self, messages):
        if not self._llm:
            return 'Erro: Modelo GGUF não carregado.'
            
        with self._lock:
            try:
                resultado = self._llm.create_chat_completion(
                    messages=messages,
                    max_tokens=800,
                    temperature=0.2,
                    top_p=0.9,
                    repeat_penalty=1.1,
                    stop=['<|end|>', '<|endoftext|>', '<|user|>'],
                )
                return resultado['choices'][0]['message']['content'].strip()
            except Exception as e:
                traceback.print_exc()
                if "llama_decode" in str(e) or "access violation" in str(e).lower():
                    print(f"[ERRO CRÍTICO MEMÓRIA] {e}", flush=True)
                return f'Erro ao gerar resposta (GGUF): {e}'

    def _gerar_safetensors(self, messages):
        try:
            from transformers import GenerationConfig
            full_prompt = self._tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            gen_config = GenerationConfig(
                max_new_tokens=500, temperature=0.3, do_sample=True,
                eos_token_id=[32000, 32001, 32007], pad_token_id=32000,
            )
            output = self._pipe(full_prompt, generation_config=gen_config, return_full_text=False)
            return output[0]['generated_text'].strip()
        except Exception as e:
            traceback.print_exc()
            return f'Erro ao gerar resposta (Transformers): {e}'
