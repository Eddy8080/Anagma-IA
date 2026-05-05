# -*- coding: utf-8 -*-
"""
Motor de Inferência da Anagma IA.
Backend : llama-cpp-python com Meta Llama 3 8B GGUF (Digiana 8B)
"""
import os
import traceback
import threading
import gc
import re
from django.conf import settings
from .rag_engine import AnagmaRAGEngine
from .vocabulario import (
    SAUDACOES, GATILHOS_SOBRE_IA, PARES_SOBRE_IA,
    GATILHOS_FORA_DO_DOMINIO, PARES_FORA_DO_DOMINIO,
    TERMOS_DETECCAO_INGLES
)


class AnagmaLLMEngine:
    """Motor unificado de alta performance (Meta Llama 3 8B)."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.rag = AnagmaRAGEngine()
                cls._instance._backend = None
                cls._instance._llm = None
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
            config.modelo_em_uso = 'DIGIANA 8B'
            if erro:
                config.ultimo_erro = str(erro)
            config.save()
        except Exception:
            pass

    def _load_model(self):
        """Carrega o motor Digiana 8B (Llama 3)."""
        self._update_status("Iniciando ativação da Digiana...", 10)
        gguf_path = os.path.abspath(getattr(settings, 'GGUF_MODEL_PATH', ''))
        
        if os.path.exists(gguf_path):
            self._update_status("Carregando inteligência contábil...", 40)
            self._update_status("Sincronizando bibliotecas...", 70)
            self._carregar_gguf(gguf_path)
            self._update_status("Motor pronto para uso!", 100, status='PRONTO')
        else:
            self._update_status("Erro: Arquivo do modelo não encontrado.", 0, status='ERRO', erro='Arquivo ausente')

    def _limpar_memoria(self):
        """Expurga modelos anteriores da RAM."""
        self._llm = None
        self._backend = None
        gc.collect()

    def recarregar_modelo(self):
        """Interface pública para reinicializar o cérebro da Digiana."""
        with self._lock:
            self._limpar_memoria()
            self._load_model()

    def _carregar_gguf(self, model_path):
        try:
            from llama_cpp import Llama
            import psutil

            ram_antes = psutil.virtual_memory().used / 1e9
            print(f'[SISTEMA] Ativando Cérebro Digiana 8B: {model_path}', flush=True)

            # Otimização: Uso equilibrado de threads para evitar saturação do sistema
            cpu_count = os.cpu_count() or 4
            n_threads = min(8, max(1, cpu_count - 1))

            self._llm = Llama(
                model_path=model_path,
                n_ctx=16384,
                n_threads=n_threads,
                n_batch=512,
                n_gpu_layers=0,
                verbose=False,
            )
            self._backend = 'gguf'

            ram_depois = psutil.virtual_memory().used / 1e9
            print(f'[SISTEMA] RAM Alocada: {ram_depois - ram_antes:.1f} GB | Threads: {n_threads}', flush=True)
            print('[SISTEMA] --- SUCESSO: DIGIANA 8B ESTÁ PRONTA ---\n', flush=True)

        except MemoryError:
            print('[ERRO CRÍTICO] RAM insuficiente para o modelo 8B.', flush=True)
        except Exception as e:
            print(f'[ERRO CRÍTICO] Falha ao carregar motor: {e}', flush=True)
            traceback.print_exc()

    # ------------------------------------------------------------------
    # Self-Audit: verificação de relevância entre RAG e LLM
    # ------------------------------------------------------------------

    def _self_audit_documentos(self, query, blocos):
        """
        Etapa de verificação entre o RAG e o LLM.
        Usa o próprio modelo para avaliar quais blocos de contexto respondem
        diretamente à pergunta, descartando os que tratam de outro assunto.
        Arquitetura geral — sem hard-code de domínios ou temas.
        """
        if not blocos or not self._llm:
            return blocos

        lista = ""
        for i, bloco in enumerate(blocos):
            linhas = bloco.strip().split('\n')
            cabecalho = linhas[0][:80] if linhas else ''
            trecho = ' '.join(linhas[1:6])[:400] if len(linhas) > 1 else ''
            lista += f"[{i+1}] {cabecalho}\n    {trecho}\n\n"

        prompt = (
            f'Pergunta: "{query}"\n\n'
            f"Documentos recuperados:\n{lista}"
            f"Para cada documento, responda SIM apenas se ele contém dados específicos que RESPONDEM a pergunta "
            f"(regras, valores, procedimentos, obrigações sobre o assunto perguntado). "
            f"Responda NÃO se o documento trata de outro assunto OU aborda o mesmo tema mas sem dados que respondam a pergunta.\n"
            f"Responda APENAS neste formato sem espaços: [1]:SIM [2]:NÃO [3]:SIM\n"
            f"Resposta:"
        )

        try:
            with self._lock:
                resultado = self._llm.create_chat_completion(
                    messages=[{'role': 'user', 'content': prompt}],
                    max_tokens=80,
                    temperature=0.0,
                    stop=['\n\n', '<|end|>', '<|endoftext|>'],
                )
            resposta = resultado['choices'][0]['message']['content'].strip()
            print(f"[SELF-AUDIT] Veredicto: {resposta}", flush=True)

            aprovados = []
            for i, bloco in enumerate(blocos):
                match = re.search(rf'\[{i+1}\]:\s*(SIM|NÃO|NAO|YES|NO)\b', resposta, re.IGNORECASE)
                if match and match.group(1).upper() in ('NÃO', 'NAO', 'NO'):
                    print(f"[SELF-AUDIT] Descartado: {bloco.split(chr(10))[0][:70]}", flush=True)
                else:
                    aprovados.append(bloco)

            if not aprovados:
                print("[SELF-AUDIT] Nenhum documento aprovado — modo conhecimento geral ativado.", flush=True)

            return aprovados

        except Exception as e:
            print(f"[SELF-AUDIT ERRO] {e}", flush=True)
            return blocos

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

    def _montar_resposta_biblioteca(self, contexto_rag, primeiro_nome):
        """
        Extrai conteúdo de documentos/ideias do banco e monta resposta diretamente,
        sem passar pelo LLM. Garante fidelidade total aos dados da biblioteca.
        Retorna None se não encontrar blocos reconhecíveis (fallback para o modelo).
        """
        import re
        blocos = []

        # Extrai blocos de DOCUMENTO APROVADO
        for match in re.finditer(
            r'DOCUMENTO APROVADO \(([^)]+)\):\n(.*?)(?=\n\n=== CONTEXTO ADICIONAL ===|IDEIA DO BANCO|INSTRUÇÃO DE CURADORIA|$)',
            contexto_rag, re.DOTALL
        ):
            nome_doc = match.group(1).strip()
            conteudo = match.group(2).strip()
            if conteudo:
                blocos.append(('documento', nome_doc, conteudo[:1500]))

        # Extrai blocos de IDEIA REGISTRADA
        for match in re.finditer(
            r'IDEIA REGISTRADA \((?:Tema: )?([^)]+)\):\n(.*?)(?=\n\n---|\n\n=== CONTEXTO ADICIONAL ===|DOCUMENTO APROVADO|CONHECIMENTO OFICIAL|INSTRUÇÃO DE CURADORIA|$)',
            contexto_rag, re.DOTALL
        ):
            titulo_ideia = match.group(1).strip()
            conteudo = match.group(2).strip()
            if conteudo:
                blocos.append(('ideia', titulo_ideia, conteudo[:1500]))

        # Extrai blocos de INSTRUÇÃO DE CURADORIA (RLHF)
        for match in re.finditer(
            r'INSTRUÇÃO DE CURADORIA APROVADA \(([^)]+)\):\nPergunta do Usuário:.*?\nResposta Ideal \(Siga este padrão\): (.*?)(?=\n\n=== CONTEXTO ADICIONAL ===|DOCUMENTO APROVADO|IDEIA DO BANCO|$)',
            contexto_rag, re.DOTALL
        ):
            titulo_cor = match.group(1).strip()
            resposta_ideal = match.group(2).strip()
            if resposta_ideal:
                blocos.append(('rlhf', titulo_cor, resposta_ideal[:1500]))

        if not blocos:
            return None

        # Monta resposta estruturada a partir dos blocos encontrados
        partes = []
        for tipo, fonte, conteudo in blocos:
            if tipo == 'rlhf':
                partes.append(conteudo)
            elif tipo == 'documento':
                partes.append(f"Com base no documento **{fonte}** da Biblioteca da Digiana:\n\n{conteudo}")
            else:
                partes.append(f"**{fonte}**\n\n{conteudo}")

        resposta = "\n\n---\n\n".join(partes)

        # Adiciona convite ao final se houver mais de um bloco
        if len(blocos) > 1:
            resposta += f"\n\nTem mais alguma dúvida sobre esse ou outro tema contábil, {primeiro_nome}?"

        return resposta

    def _extrair_contexto_institucional(self, perfil_texto):
        """
        Extrai o bloco narrativo/institucional do perfil cultural para enriquecer
        respostas de identidade nos interceptores. Suporta diferentes nomes de seção.
        Retorna string vazia se não encontrar.
        """
        if not perfil_texto:
            return ''
        import re
        padrao = re.search(
            r'(?:\d+\.\s*)?(?:CONTEXTO\s+INSTITUCIONAL|FUNDAÇÃO|HISTÓRIA|SOBRE\s+NÓS|ORIGEM)[^\n]*\n(.*)',
            perfil_texto,
            re.IGNORECASE | re.DOTALL
        )
        if not padrao:
            return ''
        trecho = padrao.group(1).strip()
        # Remove linhas que parecem início de outra seção numerada
        trecho = re.sub(r'\n\d+\.\s+[A-ZÁÉÍÓÚÀÃÕÂÊÎÔÛÇ]+[:\s]', '', trecho).strip()
        return trecho[:500]

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

    def gerar_resposta_stream(self, user_query, chat_history=None, user_name=None, saudacao=None, search_query=None, user=None):
        """
        Versão de streaming com MODO DE SEGURANÇA DE DOMÍNIO FECHADO.
        """
        try:
            if not self.pronto:
                yield "Erro: Motor de IA não disponível."
                return

            nome = user_name or 'usuário'
            primeiro_nome = nome.split()[0] if nome else nome
            cumprimento = saudacao or 'Boa tarde'
            perfil_anagma = self._get_perfil_anagma()
            is_first_message = not bool(chat_history)

            # 1. Interceptores Rápidos
            if self._e_saudacao(user_query) or self._e_fora_do_dominio(user_query) or self._e_pergunta_sobre_ia(user_query):
                yield self.gerar_resposta(user_query, chat_history, user_name, saudacao, search_query, user)
                return

            # 2. Busca RAG Soberana + Self-Audit
            excel_bloco = None        # garantia de escopo para o loop de streaming
            doc_integral_bloco = None
            try:
                blocos_rag, has_db_hits = self.rag.buscar_documentos(search_query or user_query, user=user)

                # --- INTERCEPTOR ARQUITETURAL DE EXCEL (MODO TERMINAL) ---
                excel_bloco = next((b for b in blocos_rag if "ARQUIVO EXCEL INTEGRAL DA CURADORIA" in b), None)
                # --- INTERCEPTOR DE DOCUMENTO LONGO NÃO-EXCEL (MODO TRANSCRIÇÃO) ---
                doc_integral_bloco = next((b for b in blocos_rag if "DOCUMENTO INTEGRAL DA CURADORIA" in b), None) if not excel_bloco else None

                if excel_bloco:
                    system_msg = f"""VOCÊ É UM TERMINAL DE EXIBIÇÃO FIEL.
SUA ÚNICA TAREFA: Transcrever INTEGRALMENTE as tabelas abaixo.

### REGRAS TÉCNICAS:
1. NÃO adicione saudações, comentários ou conclusões.
2. NÃO use reticências (...) e NÃO resuma.
3. Transcreva cada aba (## Aba: ...) e sua respectiva tabela em formato markdown puro.
4. Mantenha a linha de separação (| --- | --- |) imediatamente após o cabeçalho.
5. NUNCA envolva o conteúdo em cercas de código (``` ou ```markdown). Saída direta, sem wrapper.
6. Se o arquivo for maior que seu limite, transcreva até onde conseguir.

### CONTEÚDO PARA TRANSCRIÇÃO:
{excel_bloco}

ATENÇÃO: Sua resposta começa AGORA. A primeira linha DEVE ser "## Aba:" ou "|". Nenhum texto introdutório é permitido."""

                elif doc_integral_bloco:
                    system_msg = f"""VOCÊ É UM TRANSCRITOR FIEL DE DOCUMENTOS.
SUA ÚNICA TAREFA: Reproduzir o conteúdo abaixo de forma INTEGRAL e FIEL, sem interpretação.

### REGRAS:
1. NÃO adicione saudações, comentários, títulos extras ou conclusões.
2. NÃO resuma e NÃO interprete — reproduza cada parágrafo, seção e dado exatamente como está.
3. NÃO use reticências (...) para indicar corte — se atingir o limite de tokens, encerre de forma limpa na última frase completa.
4. Preserve a hierarquia de títulos (#, ##, ###) e a formatação original do documento.
5. Se houver tabelas no conteúdo, mantenha-as em formato markdown (| col | col |).

### CONTEÚDO PARA TRANSCRIÇÃO:
{doc_integral_bloco}

Comece a transcrição imediatamente, sem texto introdutório."""

                elif has_db_hits:
                    blocos_rag = self._self_audit_documentos(user_query, blocos_rag)
                    has_db_hits = bool(blocos_rag)
                    contexto_rag = "\n\n---\n\n".join(blocos_rag)
                    if contexto_rag and len(contexto_rag) > 25000:
                        contexto_rag = contexto_rag[:25000] + "... [Truncado]"
                    
                    # Detecta se há algum Excel no meio dos blocos para decidir o nível de instrução
                    tem_excel = "ARQUIVO EXCEL INTEGRAL" in contexto_rag
                    
                    instr_excel = ""
                    if tem_excel:
                        instr_excel = """
1. Se houver um bloco marcado como "ARQUIVO EXCEL INTEGRAL", seu único trabalho é transcrever TODAS as abas e tabelas contidas nele, do início ao fim.
2. NUNCA resuma, nunca use reticências (...) e nunca invente ou oculte dados.
3. Se o conteúdo for uma tabela, use obrigatoriamente a linha de separação (| --- |)."""

                    regra_ouro_excel = ""
                    if tem_excel:
                        regra_ouro_excel = """
### REGRA DE OURO PARA EXCEL (DIRETRIZ UNIVERSAL):
1. Se você encontrar nomes de abas (ex: "## Aba: Parte A"), você DEVE transcrever o nome da aba e a tabela correspondente logo abaixo.
2. Repita isso para TODAS as abas encontradas no contexto.
3. A exibição deve ser INTEGRAL e FIEL ao arquivo original, agindo apenas como um meio de visualização."""

                    system_msg = f"""Você é a **Digiana**, assistente oficial de contabilidade da **Anagma**.

### MODO: BIBLIOTECA INTERNA ATIVA

### FORMATO DE RESPOSTA OBRIGATÓRIO
Você DEVE responder sempre neste formato de duas seções, sem exceção:

**Verificação:**
Transcreva LITERALMENTE os trechos dos documentos abaixo que fundamentam sua resposta.
— Se o dado não estiver no texto, declare explicitamente que a informação está ausente no documento consultado.
— NÃO inclua saudações ou interpretações nesta seção.{instr_excel}

**Resposta:**
Responda baseando-se EXCLUSIVAMENTE no que foi declarado em Verificação acima.
— PRIORIDADE ABSOLUTA: Use as definições e siglas conforme aparecem nos documentos (ex: PAT). Ignore definições externas se o documento trouxer uma específica.
— FORMATAÇÃO: Organize dados numéricos ou listas em tabelas markdown (| Coluna |).{regra_ouro_excel}

### CONTEXTO DA EMPRESA (DNA):
{perfil_anagma if perfil_anagma else 'Base Técnica Anagma.'}

### DADOS DA BIBLIOTECA INTERNA (FONTE ÚNICA DE VERDADE):
{contexto_rag}"""
                else:
                    system_msg = f"""Você é a **Digiana**, assistente oficial de contabilidade da **Anagma**.

### MODO: BIBLIOTECA OMISSA

### FORMATO DE RESPOSTA OBRIGATÓRIO
Você DEVE responder neste formato de duas seções, sem exceção:

**Verificação:**
Escreva exatamente: "Nenhum documento encontrado na biblioteca da Anagma sobre [descreva o assunto da pergunta]."

**Resposta:**
— Informe que a biblioteca não possui registros específicos sobre este tema.
— Indique a fonte oficial adequada (Receita Federal, Portal do Simples Nacional, eSocial, Prefeitura, etc.).
— NUNCA gere tabelas, valores, alíquotas, datas ou obrigações específicas se a biblioteca for omissa. Se você fizer isso, estará cometendo um erro grave de segurança contábil.
— Encerre recomendando a consulta à fonte oficial.

### CONTEXTO DA EMPRESA:
{perfil_anagma if perfil_anagma else 'Base Técnica Anagma.'}"""

            except Exception as e:
                print(f"[ERRO RAG] {e}", flush=True)
                system_msg = f"""Você é a **Digiana**, assistente oficial de contabilidade da **Anagma**.
Ocorreu um erro ao consultar a biblioteca. Por favor, tente reformular a pergunta."""

            # 4. Gestão de Mensagens com controle de budget de tokens
            # n_ctx=16384, reservamos 1500 para a resposta → ~14000 disponíveis para input
            MAX_INPUT_TOKENS = 14000
            tokens_sistema = self._contar_tokens_aprox(system_msg)
            tokens_query   = self._contar_tokens_aprox(user_query)
            budget_historico = MAX_INPUT_TOKENS - tokens_sistema - tokens_query

            messages = [{'role': 'system', 'content': system_msg}]
            if chat_history and budget_historico > 0:
                usados = 0
                historico_filtrado = []
                for msg in reversed(chat_history):
                    if msg.get('role') in ('user', 'assistant') and msg.get('content'):
                        t = self._contar_tokens_aprox(msg['content'])
                        if usados + t < budget_historico:
                            historico_filtrado.insert(0, {'role': msg['role'], 'content': msg['content']})
                            usados += t
                        else:
                            break
                messages.extend(historico_filtrado)
            messages.append({'role': 'user', 'content': user_query})

            # 5. Loop de Streaming
            # Modo Excel recebe budget máximo; Modo Transcrição (PDF longo) recebe budget elevado.
            if excel_bloco:
                max_tokens_saida = 4096
            elif doc_integral_bloco:
                max_tokens_saida = 3000
            else:
                max_tokens_saida = 1000

            # Coleta todos os tokens com o lock — serializa o acesso ao objeto C.
            # llama-cpp-python não é thread-safe; dois create_chat_completion(stream=True)
            # simultâneos no mesmo objeto Llama corrompem o KV cache interno da biblioteca.
            with self._lock:
                raw_stream = self._llm.create_chat_completion(
                    messages=messages,
                    max_tokens=max_tokens_saida,
                    temperature=0.0,
                    stream=True,
                    stop=['<|end|>', '<|endoftext|>', '<|user|>']
                )
                tokens = [
                    chunk['choices'][0]['delta']['content']
                    for chunk in raw_stream
                    if 'content' in chunk['choices'][0]['delta']
                ]

            # Lock liberado — entrega os tokens coletados ao cliente via SSE.
            if excel_bloco:
                # Modo Terminal: descarta deterministicamente qualquer preamble
                # antes do início real da tabela (## Aba: ou |)
                buffer_pre = ""
                tabela_iniciada = False
                for token in tokens:
                    if not tabela_iniciada:
                        buffer_pre += token
                        idx = -1
                        for marcador in ('## ', '|'):
                            pos = buffer_pre.find(marcador)
                            if pos >= 0:
                                idx = pos if idx < 0 else min(idx, pos)
                        if idx >= 0:
                            tabela_iniciada = True
                            yield buffer_pre[idx:]
                        elif len(buffer_pre) > 400:
                            tabela_iniciada = True
                            yield buffer_pre
                    else:
                        yield token
            else:
                for token in tokens:
                    yield token

        except Exception as e:
            traceback.print_exc()
            yield f" Erro no processamento: {str(e)}"


    def gerar_resposta(self, user_query, chat_history=None, user_name=None, saudacao=None, search_query=None, user=None):
        """
        Gera resposta usando RAG + Llama 3 com gestão de contexto e thread-safety.
        """
        if not self.pronto:
            return 'Desculpe, o motor de IA não está disponível. Verifique os logs do servidor.'

        import random

        # Contexto base computado uma vez — usado por todos os interceptores e pelo sistema
        is_first_message = not bool(chat_history)
        nome = user_name or 'usuário'
        primeiro_nome = nome.split()[0] if nome else nome
        cumprimento = saudacao or 'Boa tarde'

        # Perfil carregado cedo (cache < 1ms) para estar disponível nos interceptores
        perfil_anagma = self._get_perfil_anagma()

        # Intercepta saudações simples
        if self._e_saudacao(user_query):
            query_l = user_query.lower()
            resp_cumprimento = cumprimento
            if 'bom dia' in query_l: resp_cumprimento = "Bom dia"
            elif 'boa tarde' in query_l: resp_cumprimento = "Boa tarde"
            elif 'boa noite' in query_l: resp_cumprimento = "Boa noite"
            elif 'olá' in query_l or 'ola' in query_l: resp_cumprimento = "Olá"
            elif 'oi' in query_l: resp_cumprimento = "Olá"

            if is_first_message:
                opcoes = [
                    f"{resp_cumprimento}, {primeiro_nome}! Sou a Digiana, sua consultora técnica na Anagma. Em que posso auxiliar em suas questões contábeis hoje?",
                    f"{resp_cumprimento}, {primeiro_nome}. Estou à disposição para analisar seus documentos e esclarecer dúvidas fiscais. Por onde gostaria de começar?",
                    f"{resp_cumprimento}! Seja bem-vindo à inteligência da Anagma, {primeiro_nome}. Qual tema técnico vamos abordar agora?",
                ]
            else:
                opcoes = [
                    f"{resp_cumprimento}, {primeiro_nome}! Prossiga com sua dúvida. Em que mais posso contribuir para sua análise contábil?",
                    f"{resp_cumprimento}. Estou aqui para ajudar. Qual o próximo ponto técnico que deseja discutir?",
                    f"{resp_cumprimento}, {primeiro_nome}. Compreendido. Deseja aprofundar algum assunto da nossa base de documentos ou ideias?",
                ]
            return random.choice(opcoes)

        # Intercepta perguntas sobre a própria IA e suas fontes de conhecimento
        if self._e_pergunta_sobre_ia(user_query):
            # Contexto institucional do perfil cultural (quem somos, origem, propósito)
            contexto_inst = self._extrair_contexto_institucional(perfil_anagma)
            nota_perfil = f"\n\n{contexto_inst}\n" if contexto_inst else '\n'

            base_conhecimento = (
                f"\nMinhas respostas combinam meu conhecimento de treinamento com o conhecimento interno registrado pela equipe:\n"
                f"- **Documentos da empresa** — PDFs e arquivos enviados e aprovados.\n"
                f"- **Banco de Ideias** — orientações e boas práticas registradas pelos colaboradores.\n"
                f"- **Aprendizado contínuo** — cada correção feita pelos responsáveis melhora minhas respostas futuras.\n\n"
                f"Quanto mais a equipe registra, mais precisa e assertiva fico. É só perguntar!"
            )

            if is_first_message:
                opcoes = [
                    (
                        f"Sou a **Digiana**, assistente de contabilidade e tributos da **Anagma**, {primeiro_nome}!"
                        f"{nota_perfil}"
                        f"Posso ajudar com impostos, folha de pagamento, notas fiscais, obrigações da empresa e muito mais. "
                        f"Se quiser, também posso analisar um documento — é só anexar aqui no chat."
                        f"{base_conhecimento}"
                        f"O que você quer resolver hoje?"
                    ),
                    (
                        f"{cumprimento}, {primeiro_nome}! Sou a Digiana, especialista em contabilidade aqui na Anagma."
                        f"{nota_perfil}"
                        f"Tire dúvidas sobre impostos, regimes de tributação, folha de pagamento, escrituração e documentos fiscais. "
                        f"Pode me enviar PDFs e imagens direto no chat para eu analisar."
                        f"{base_conhecimento}"
                        f"Por onde quer começar?"
                    ),
                    (
                        f"Aqui é a **Digiana**, {primeiro_nome}! Sou a assistente contábil da Anagma."
                        f"{nota_perfil}"
                        f"Minhas respostas vêm do conhecimento interno da equipe — não faço buscas genéricas na internet. "
                        f"Trabalho com o que a própria Anagma registrou: documentos, orientações e experiência acumulada."
                        f"{base_conhecimento}"
                        f"Tem alguma dúvida?"
                    ),
                ]
            else:
                # Conversa em andamento — explica o ciclo de aprendizado de forma precisa e simples
                opcoes = [
                    (
                        f"Sim! O aprendizado é automático e contínuo, {primeiro_nome}.\n\n"
                        f"Quando a equipe registra uma **nova ideia** e o responsável a ativa, já passo a usar esse conhecimento nas próximas respostas — na hora, sem reiniciar o sistema.\n"
                        f"O mesmo vale para **documentos enviados à Biblioteca**: assim que aprovados, o conteúdo é incorporado automaticamente.\n"
                        f"E quando um responsável **corrige uma resposta minha**, essa correção guia minhas respostas futuras em situações parecidas.\n\n"
                        f"Quanto mais a equipe contribui, mais precisa fico. O que mais queria saber?"
                    ),
                    (
                        f"Exatamente, {primeiro_nome}! Funciona assim:\n\n"
                        f"- **Nova ideia ativada** → já uso esse conhecimento na próxima pergunta.\n"
                        f"- **Documento aprovado na Biblioteca** → conteúdo incorporado na hora.\n"
                        f"- **Correção feita por um responsável** → melhora minhas respostas em perguntas similares.\n\n"
                        f"Tudo acontece automaticamente, sem intervenção técnica. A equipe ensina, eu aprendo. Tem mais alguma dúvida?"
                    ),
                    (
                        f"Sim, {primeiro_nome}! Consulto automaticamente os documentos e orientações registrados pela equipe da Anagma. "
                        f"Tudo interno — sem busca na internet. O que mais precisa?"
                    ),
                ]
            return random.choice(opcoes)

        # Intercepta temas fora do domínio contábil (Guardrails)
        if self._e_fora_do_dominio(user_query):
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
        try:
            blocos_rag, has_db_hits = self.rag.buscar_documentos(search_query or user_query, user=user)
            # Modo Transcrição não passa pelo Self-Audit (entrega integral, sem filtro de chunks)
            doc_integral_bloco = next((b for b in blocos_rag if "DOCUMENTO INTEGRAL DA CURADORIA" in b), None)
            if has_db_hits and not doc_integral_bloco:
                blocos_rag = self._self_audit_documentos(user_query, blocos_rag)
                has_db_hits = bool(blocos_rag)
            contexto_rag = "\n\n---\n\n".join(blocos_rag)
            if contexto_rag and len(contexto_rag) > 15000:
                contexto_rag = contexto_rag[:15000] + "... [Conteúdo truncado]"
        except Exception as e:
            print(f"[ERRO RAG] {e}")
            contexto_rag, has_db_hits = "", False
            doc_integral_bloco = None

        # --- Montagem do System Message (condicional: biblioteca vs. conhecimento geral) ---
        try:
            if doc_integral_bloco:
                system_msg = f"""VOCÊ É UM TRANSCRITOR FIEL DE DOCUMENTOS.
SUA ÚNICA TAREFA: Reproduzir o conteúdo abaixo de forma INTEGRAL e FIEL, sem interpretação.

### REGRAS:
1. NÃO adicione saudações, comentários, títulos extras ou conclusões.
2. NÃO resuma e NÃO interprete — reproduza cada parágrafo, seção e dado exatamente como está.
3. Preserve a hierarquia de títulos (#, ##, ###) e a formatação original do documento.
4. Se houver tabelas no conteúdo, mantenha-as em formato markdown (| col | col |).

### CONTEÚDO PARA TRANSCRIÇÃO:
{doc_integral_bloco}"""
            elif has_db_hits:
                system_msg = f"""Você é a **Digiana**, assistente oficial de contabilidade da **Anagma**.

### MODO: BIBLIOTECA INTERNA ATIVA

### FORMATO DE RESPOSTA OBRIGATÓRIO
Você DEVE responder sempre neste formato de duas seções, sem exceção:

**Verificação:**
Aja como um ESPELHO dos documentos abaixo. 
1. Se houver um bloco marcado como "ARQUIVO EXCEL INTEGRAL", seu único trabalho é transcrever TODAS as abas e tabelas contidas nele, do início ao fim.
2. NUNCA resuma, nunca use reticências (...) e nunca invente ou oculte dados.
3. Se o conteúdo for uma tabela, use obrigatoriamente a linha de separação (| --- |).

**Resposta:**
Responda baseando-se EXCLUSIVAMENTE no que foi declarado em Verificação acima.
— Se for um arquivo Excel: transcreva o conteúdo integral aqui novamente para garantir a visualização correta.
— FORMATAÇÃO: Sempre organize dados de planilhas em tabelas markdown reais (| Coluna |). Deixe uma linha em branco antes de começar cada tabela.
— BOTÃO VISUALIZAR: Garanta que a tabela esteja bem formada para que o botão "Ver Tabela" apareça no chat.

### REGRA DE OURO PARA EXCEL (DIRETRIZ UNIVERSAL):
ESTA REGRA SE APLICA A QUALQUER ARQUIVO INSERIDO NA BIBLIOTECA DE CURADORIA EM FORMATO XLS OU XLSX. 
1. Se você encontrar nomes de abas (ex: "## Aba: Parte A"), você DEVE transcrever o nome da aba e a tabela correspondente logo abaixo. 
2. Repita isso para TODAS as abas encontradas no contexto. 
3. Nunca invente dados para preencher abas. 
4. A exibição deve ser INTEGRAL e FIEL ao arquivo original, agindo apenas como um meio de visualização para o usuário.

### CONTEXTO DA EMPRESA (DNA):
{perfil_anagma if perfil_anagma else 'Base Técnica Anagma.'}

### DADOS DA BIBLIOTECA INTERNA:
{contexto_rag}"""
            else:
                system_msg = f"""Você é a **Digiana**, assistente oficial de contabilidade da **Anagma**.

### MODO: BIBLIOTECA OMISSA

### FORMATO DE RESPOSTA OBRIGATÓRIO
Você DEVE responder neste formato de duas seções, sem exceção:

**Verificação:**
Escreva exatamente: "Nenhum documento encontrado na biblioteca da Anagma sobre [descreva o assunto da pergunta]."

**Resposta:**
— Informe que a biblioteca não possui registros específicos sobre este tema.
— Indique a fonte oficial adequada (Receita Federal, Portal do Simples Nacional, eSocial, Prefeitura, etc.).
— NUNCA gere tabelas, valores, alíquotas, datas ou obrigações específicas se a biblioteca for omissa. Se você fizer isso, estará cometendo um erro grave de segurança contábil.
— Encerre recomendando a consulta à fonte oficial.

### CONTEXTO DA EMPRESA (DNA):
{perfil_anagma if perfil_anagma else 'Base Técnica Anagma.'}"""

            # --- GESTÃO DE CONTEXTO ---
            MAX_CONTEXT_TOKENS = 7000
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

            res = self._gerar_gguf(messages)
            res_limpa = self._limpar_resposta(res)

            # KILL-SWITCH DE IDIOMA
            if self._is_ingles(res_limpa):
                opcoes = [
                    f"{cumprimento}, {primeiro_nome}! Identifiquei uma falha na geração do idioma. Como sou uma IA focada exclusivamente na contabilidade brasileira, minha comunicação deve ser em Português Brasileiro. Em que posso ajudá-lo hoje com suas dúvidas técnicas?",
                    f"{cumprimento}, {primeiro_nome}. Houve uma tentativa de resposta em idioma estrangeiro pelo modelo base. Como sua assistente técnica Digiana, mantenho meu foco apenas em Português e temas contábeis brasileiros. Como posso ser útil agora?",
                ]
                return random.choice(opcoes)

            return res_limpa

        except Exception as e:
            traceback.print_exc()
            return f"Desculpe, {primeiro_nome}, ocorreu um erro técnico ao processar sua resposta. Pode tentar reformular a pergunta?"

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
                    max_tokens=1200,
                    temperature=0.0, # Rigor total
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
