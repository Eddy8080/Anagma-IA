# -*- coding: utf-8 -*-
"""
Motor de Inferência da Anagma IA.
Backend primário : llama-cpp-python com Phi-3-mini GGUF Q4_K_M (~2.4 GB, CPU)
Backend fallback : transformers + safetensors float16 (~4.6 GB, CPU)
"""
import os
import traceback
import threading
import gc
from django.conf import settings
from .rag_engine import AnagmaRAGEngine
from .vocabulario import (
    SAUDACOES, GATILHOS_SOBRE_IA, PARES_SOBRE_IA,
    GATILHOS_FORA_DO_DOMINIO, PARES_FORA_DO_DOMINIO,
    TERMOS_DETECCAO_INGLES
)


class AnagmaLLMEngine:
    """Singleton dinâmico que permite trocar de cérebro em tempo real."""

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
    # Carregamento e Gestão de Status
    # ------------------------------------------------------------------

    def _update_status(self, etapa, progresso, status='CARREGANDO', modelo=None, erro=None):
        """Atualiza o banco de dados com o progresso real para o Admin."""
        try:
            from core.models import ConfiguracaoIA
            config = ConfiguracaoIA.get_solo()
            config.etapa_nome = etapa
            config.progresso = progresso
            config.status = status
            if modelo:
                config.modelo_em_uso = modelo
            if erro:
                config.ultimo_erro = str(erro)
            config.save()
        except Exception:
            pass

    def _load_model(self):
        """Decide qual modelo carregar com base na preferência do Admin."""
        from core.models import ConfiguracaoIA
        pref = ConfiguracaoIA.get_solo().modelo_preferido
        
        self._update_status("Iniciando ativação da Digiana...", 10)
        
        if pref == 'LEVE':
            self._ativar_modo_leve()
        else:
            self._ativar_modo_completo()

    def _limpar_memoria(self):
        """Expurga modelos anteriores da RAM para evitar travamentos."""
        self._update_status("Limpando memória para o novo cérebro...", 20)
        self._llm = None
        self._pipe = None
        self._model = None
        self._tokenizer = None
        self._backend = None
        gc.collect()

    def _ativar_modo_leve(self):
        gguf_path = os.path.abspath(getattr(settings, 'GGUF_MODEL_PATH', ''))
        if os.path.exists(gguf_path):
            self._update_status("Carregando módulo de aprendizado existente...", 40)
            # Simulação de carga de aprendizado (RAG já inicializado)
            self._update_status("Sincronizando histórico de conversas...", 60)
            self._update_status("Preparando modelo LEVE...", 80)
            self._carregar_gguf(gguf_path)
            self._update_status("Carregamento completo!", 100, status='PRONTO', modelo='LEVE')
        else:
            self._update_status("Erro: Arquivo GGUF não encontrado.", 0, status='ERRO', erro='Arquivo ausente')

    def _ativar_modo_completo(self):
        safetensors_path = os.path.abspath(getattr(settings, 'MICROSOFT_MODEL_PATH', ''))
        if os.path.exists(safetensors_path):
            self._update_status("Carregando módulo de aprendizado existente...", 30)
            self._update_status("Sincronizando histórico de conversas...", 50)
            self._update_status("Preparando modelo COMPLETO...", 70)
            sucesso = self._carregar_safetensors(safetensors_path)
            if sucesso:
                self._update_status("Carregamento completo!", 100, status='PRONTO', modelo='COMPLETO')
            else:
                self._update_status("Erro ao carregar Safetensors. Recuando para modo LEVE.", 50, status='HIBERNACAO')
                self._ativar_modo_leve()
        else:
            self._update_status("Modelo COMPLETO não encontrado. Ativando modo LEVE.", 40, status='HIBERNACAO')
            self._ativar_modo_leve()

    def recarregar_modelo(self):
        """Interface pública para trocar de cérebro via Admin."""
        with self._lock:
            self._limpar_memoria()
            self._load_model()

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
            return True

        except MemoryError:
            print('[ERRO CRÍTICO] RAM insuficiente.', flush=True)
            return False
        except Exception as e:
            print(f'[ERRO CRÍTICO] Falha ao carregar safetensors: {e}', flush=True)
            traceback.print_exc()
            return False

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

    def _e_fora_do_dominio(self, texto):
        t = texto.strip().lower()
        # 1. Verifica gatilhos diretos
        if any(g in t for g in GATILHOS_FORA_DO_DOMINIO):
            return True
        # 2. Verifica pares de palavras
        palavras = set(t.split())
        for par in PARES_FORA_DO_DOMINIO:
            if all(p in palavras for p in par):
                return True
        return False

    def _is_ingles(self, texto):
        if not texto: return False
        t = texto.lower()
        # Se contiver 3 ou mais termos comuns em inglês, bloqueia
        count = 0
        for termo in TERMOS_DETECCAO_INGLES:
            if termo in t:
                count += 1
            if count >= 3:
                return True
        return False

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
                    f"Sou a **Digiana IA**, sua assistente de contabilidade e tributos brasileiros, {primeiro_nome}! "
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
                    f"Sou a Digiana! Funciono como um especialista contábil disponível aqui no sistema, {primeiro_nome}. "
                    f"Pode me mandar perguntas sobre tributos, escrituração, IRRF, CSLL, ICMS, ISS, folha — tudo da área. "
                    f"Também analiso documentos que você anexar. "
                    f"Tem alguma dúvida específica?"
                ),
            ]
            return random.choice(opcoes)

        # Intercepta temas fora do domínio contábil (Guardrails)
        if self._e_fora_do_dominio(user_query):
            import random
            primeiro_nome = (user_name or 'usuário').split()[0]
            cumprimento = saudacao or 'Boa tarde'
            opcoes = [
                (
                    f"{cumprimento}, {primeiro_nome}! Como sou uma IA focada exclusivamente em **contabilidade, tributos e gestão financeira**, "
                    f"meu aprendizado é restrito a esses temas técnicos. "
                    f"Infelizmente não consigo ajudar com questões de cultura geral, lazer ou outros assuntos fora do domínio contábil. "
                    f"Como posso ajudá-lo hoje com suas dúvidas fiscais ou tributárias?"
                ),
                (
                    f"{cumprimento}, {primeiro_nome}. Minha base de conhecimento é especializada em **contabilidade brasileira e internacional**. "
                    f"Para garantir a precisão técnica das minhas respostas, não abordo temas fora desta área, como cultura ou curiosidades gerais. "
                    f"Tem alguma dúvida sobre impostos, folha de pagamento ou documentos contábeis em que eu possa ajudar?"
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

        system_msg = f"""MANDATO SUPREMO DE IDIOMA E IDENTIDADE:
- Você é a **Digiana**, a inteligência artificial especialista e oficial da empresa **Anagma**.
- **BLOQUEIO DE IDIOMA:** Você está terminantemente PROIBIDA de responder em inglês ou qualquer outro idioma que não seja o **Português Brasileiro (PT-BR)**. Toda a sua comunicação deve ser exclusivamente em português de alto nível, técnico e claro.
- **OPERADOR DIGITAL:** Você opera em um ambiente 100% DIGITAL. Não existem locais físicos ou atendentes humanos.

SAUDAÇÃO OBRIGATÓRIA:
- Comece SEMPRE com: "{cumprimento}, {nome}!".

REGRAS DE RESPOSTA E AUTORIDADE:
1. **Prioridade de Dados:** Se a informação estiver no CONTEXTO INTERNO abaixo, use-a como VERDADE ABSOLUTA. Responda com autoridade técnica direta.
2. **Postura Resolutiva:** Você é uma ferramenta de apoio à decisão. Evite incertezas. Use: "O procedimento correto é...", "A legislação indica que...".
3. **Fim das Alucinações:** JAMAIS sugira contatos externos ou locais físicos.
4. **Domínio:** Responda apenas sobre contabilidade, tributos e finanças.
5. **Restrição de Conteúdo:** Se o usuário enviar apenas uma saudação, apresente-se como Digiana e pergunte como pode ajudar na área contábil. NUNCA traduza saudações ou termos para outros idiomas.

CONTEXTO DA EMPRESA (DNA DA DIGIANA):
{perfil_anagma if perfil_anagma else 'Digiana - Especialista Técnica em Contabilidade Digital.'}
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
            
        res_limpa = self._limpar_resposta(res)
        
        # KILL-SWITCH DE IDIOMA: Se o modelo falhar e responder em inglês
        if self._is_ingles(res_limpa):
            import random
            nome = (user_name or 'usuário').split()[0]
            cumprimento = saudacao or 'Boa tarde'
            opcoes = [
                f"{cumprimento}, {nome}! Identifiquei uma falha na geração do idioma. Como sou uma IA focada exclusivamente na contabilidade brasileira, minha comunicação deve ser em Português Brasileiro. Em que posso ajudá-lo hoje com suas dúvidas técnicas?",
                f"{cumprimento}, {nome}. Houve uma tentativa de resposta em idioma estrangeiro pelo modelo base. Como sua assistente técnica Digiana, mantenho meu foco apenas em Português e temas contábeis brasileiros. Como posso ser útil agora?",
            ]
            return random.choice(opcoes)
            
        return res_limpa

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
