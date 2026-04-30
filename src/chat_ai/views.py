from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.cache import cache
from django.utils import timezone
from django.utils.html import strip_tags
from django.views.decorators.cache import never_cache
from datetime import timedelta
from .models import ChatSession, ChatMessage
from django.views.decorators.http import require_POST
from .llm_engine import AnagmaLLMEngine
from .document_processor import AnagmaDocumentProcessor
from core.models import DocumentoBiblioteca
import json
import re

_llm_engine = None

@login_required
@require_POST
def upload_document(request):
    """
    Recebe um arquivo, extrai texto e salva na Biblioteca.
    Superusuário: aprovação e vetorização imediatas — disponível no RAG na mesma requisição.
    Usuário comum: status 'pending', aguarda auditoria do superusuário.
    """
    if 'file' not in request.FILES:
        return JsonResponse({'status': 'error', 'message': 'Nenhum arquivo enviado'}, status=400)

    uploaded_file = request.FILES['file']
    session_id = request.POST.get('session_id')
    nome_original = uploaded_file.name
    ext = nome_original.split('.')[-1].lower() if '.' in nome_original else ''
    is_superuser = request.user.is_superuser

    extensoes_usuario = ['pdf', 'png', 'jpg', 'jpeg']
    extensoes_superuser = ['pdf', 'png', 'jpg', 'jpeg', 'docx', 'doc', 'xlsx', 'xls', 'txt']
    extensoes_permitidas = extensoes_superuser if is_superuser else extensoes_usuario

    if ext not in extensoes_permitidas:
        return JsonResponse({'status': 'error', 'message': 'Extensão não suportada'}, status=400)

    try:
        # 1. Salva na Biblioteca
        doc_bib = DocumentoBiblioteca.objects.create(
            nome_arquivo=nome_original,
            arquivo=uploaded_file,
            extensao=ext,
            status='approved' if is_superuser else 'pending',
            enviado_por=request.user,
            auditado_por=request.user if is_superuser else None,
            processado_em=timezone.now() if is_superuser else None,
        )

        # 2. Extrai texto
        doc_bib.arquivo.open('rb')
        try:
            texto_extraido, meta_extracao = AnagmaDocumentProcessor.extrair_texto(doc_bib.arquivo, ext)
        finally:
            doc_bib.arquivo.close()
        doc_bib.conteudo_extraido = texto_extraido
        doc_bib.processado_em = timezone.now()
        doc_bib.save(update_fields=['conteudo_extraido', 'processado_em'])

        # 3. Superusuário: vetoriza imediatamente no ChromaDB
        if is_superuser and texto_extraido and not texto_extraido.startswith('Erro'):
            try:
                from django.utils.html import strip_tags
                llm_engine = get_llm_engine()
                llm_engine.rag.vetorizar_texto(strip_tags(texto_extraido), nome_original)
                print(f"[UPLOAD CHAT] '{nome_original}' vetorizado imediatamente pelo superusuário.", flush=True)
            except Exception as e_rag:
                print(f"[UPLOAD CHAT] Aviso: falha ao vetorizar '{nome_original}': {e_rag}", flush=True)

        # 4. Gerenciar Sessão de Chat
        if session_id:
            try:
                session = ChatSession.objects.get(id=session_id, user=request.user)
            except ChatSession.DoesNotExist:
                session = ChatSession.objects.create(user=request.user, titulo=f"Anexo: {nome_original}")
        else:
            session = ChatSession.objects.create(user=request.user, titulo=f"Anexo: {nome_original}")

        # 5. Registra no Chat (Mensagem do Usuário)
        ChatMessage.objects.create(session=session, role='user', content=f"[Anexo enviado: {nome_original}]")

        # 6. Resposta diferenciada por perfil
        trecho = (texto_extraido[:300].replace('\n', ' ') if texto_extraido else "Conteúdo técnico em análise")
        if is_superuser:
            ai_response = (
                f"Documento **{nome_original}** recebido e integrado diretamente à Biblioteca de Curadoria. "
                f"Identifiquei que ele contém informações sobre: *{trecho}...*"
                f"\n\n✅ O conteúdo já está **ativo na memória da Digiana** e disponível para consultas nesta sessão."
                f"\n\nPode perguntar sobre o documento agora mesmo."
            )
        else:
            ai_response = (
                f"Recebi o documento **{nome_original}**. "
                f"Identifiquei preliminarmente que ele contém informações sobre: *{trecho}...* "
                f"\n\nO conteúdo foi encaminhado para a **Biblioteca de Curadoria** e está em **processo de auditoria** "
                f"pelos superusuários para garantir a precisão técnica antes de ser integrado ao meu aprendizado contábil."
                f"\n\nEnquanto isso, no que mais posso ajudar você hoje?"
            )

        ai_msg = ChatMessage.objects.create(session=session, role='assistant', content=ai_response)
        session.save()

        return JsonResponse({
            'status': 'success',
            'session_id': session.id,
            'session_title': session.titulo,
            'response': ai_response,
            'message_id': ai_msg.id,
            'time': timezone.localtime().strftime('%H:%M'),
        })

    except Exception as e:
        print(f"[ERRO UPLOAD CHAT] {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=200)


def get_llm_engine():
    global _llm_engine
    if _llm_engine is None:
        _llm_engine = AnagmaLLMEngine()
    return _llm_engine


def _get_saudacao():
    hora = timezone.localtime().hour
    if 5 <= hora < 12:
        return 'Bom dia'
    elif 12 <= hora < 18:
        return 'Boa tarde'
    return 'Boa noite'


def _get_ideias_ativas():
    ideias = cache.get('global_ideias')
    if ideias is None:
        from core.models import GlobalIdeia
        qs = GlobalIdeia.objects.filter(ativa=True).values('titulo', 'conteudo').order_by('criado_em')
        ideias = [{'titulo': i['titulo'], 'conteudo': strip_tags(i['conteudo'])} for i in qs]
        cache.set('global_ideias', ideias, timeout=300)
    return ideias


_PADROES_CONTINUACAO = re.compile(
    r'\b(continue|continua[r]?|exiba?\s+o?\s*(restante|resto|mais)|'
    r'mostr[ae]\s+o?\s*(restante|resto|mais)|a\s+partir\s+de|'
    r'pr[oó]xima?\s+(parte|se[cç][aã]o|aba))\b',
    re.IGNORECASE
)


def _detectar_excel_continuacao(session, user_prompt):
    """
    Retorna o nome do arquivo Excel se a mensagem for continuação de exibição de planilha.
    Dupla verificação: (1) padrão de continuação no texto + (2) última resposta da IA tem '## Aba:'.
    """
    if not _PADROES_CONTINUACAO.search(user_prompt):
        return None
    ultima_ia = session.messages.filter(role='assistant').order_by('-timestamp').first()
    if not ultima_ia or '## Aba:' not in ultima_ia.content:
        return None
    from django.db.models import Q
    xlsx_aprovados = DocumentoBiblioteca.objects.filter(
        Q(status='approved') & (Q(nome_arquivo__icontains='.xls') | Q(nome_arquivo__icontains='.xlsx'))
    )
    for msg_u in session.messages.filter(role='user').order_by('-timestamp')[:8]:
        palavras = [p for p in msg_u.content.lower().split() if len(p) > 3]
        for doc_x in xlsx_aprovados:
            if any(p in doc_x.nome_arquivo.lower() for p in palavras):
                return doc_x.nome_arquivo
    return None


def _verificar_truncamento_excel(search_query, full_response, user=None):
    """
    Detecta exibição parcial de planilha comparando abas no arquivo vs. na resposta.
    Retorna mensagem de aviso ou None. Link direcionado por papel do usuário.
    """
    if '## Aba:' not in full_response:
        return None
    try:
        from django.db.models import Q
        palavras = [p for p in search_query.lower().split() if len(p) > 3]
        xlsx_aprovados = DocumentoBiblioteca.objects.filter(
            Q(status='approved') & (Q(nome_arquivo__icontains='.xls') | Q(nome_arquivo__icontains='.xlsx'))
        )
        doc_alvo = None
        for doc_x in xlsx_aprovados:
            if doc_x.nome_arquivo.lower() == search_query.lower() or \
               any(p in doc_x.nome_arquivo.lower() for p in palavras):
                doc_alvo = doc_x
                break
        if not doc_alvo or not doc_alvo.conteudo_extraido:
            return None
        abas_arquivo = doc_alvo.conteudo_extraido.count('## Aba:')
        abas_resposta = full_response.count('## Aba:')
        if abas_arquivo > abas_resposta:
            link = '/admin-panel/biblioteca/' if (user and user.is_superuser) else '/biblioteca/'
            label = 'Painel Admin → Biblioteca' if (user and user.is_superuser) else 'Biblioteca'
            return (
                f"\n\n---\n"
                f"> ⚠️ **Exibição parcial** — o arquivo possui {abas_arquivo} aba(s) e "
                f"{abas_resposta} foi(foram) exibida(s). Limite de geração atingido. "
                f"Acesse **[{label}]({link})** para ver o conteúdo extraído completo."
            )
    except Exception:
        pass
    return None


def _manual_usuario(nome):
    return (
        f"# 📖 Guia da Digiana\n\n"
        f"Olá, **{nome}**! Tudo que você precisa saber para usar a Digiana com eficiência.\n\n"
        "---\n\n"
        "## ⚡ Começo rápido\n\n"
        "Basta digitar — perguntas em linguagem natural funcionam diretamente:\n\n"
        "> *\"Qual a alíquota do DAS para MEI em 2024?\"*\n"
        "> *\"Quais são as obrigações acessórias do Simples Nacional?\"*\n"
        "> *\"Como funciona o PGDAS-D?\"*\n"
        "> *\"Qual o prazo de entrega da ECD?\"*\n\n"
        "**Dica:** quanto mais específica a pergunta, mais precisa a resposta. "
        "Inclua ano, regime tributário ou artigo quando souber.\n\n"
        "---\n\n"
        "## 📋 Como as respostas funcionam\n\n"
        "Toda resposta chega em **duas partes fixas**:\n\n"
        "| Bloco | O que contém |\n"
        "|---|---|\n"
        "| **Verificação** | Trecho literal copiado do documento da biblioteca que responde sua pergunta |\n"
        "| **Resposta** | Interpretação baseada *exclusivamente* na Verificação acima |\n\n"
        "Se a biblioteca não tiver o dado, a Digiana informa explicitamente e indica "
        "a **fonte oficial** (Receita Federal, Portal do Simples Nacional) — "
        "**nunca inventa valores, alíquotas ou artigos**.\n\n"
        "---\n\n"
        "## 📚 Biblioteca\n\n"
        "Clique em **📚 Biblioteca** na barra lateral para abrir o catálogo de documentos aprovados.\n\n"
        "- **Busca instantânea** — filtre pelo nome do arquivo sem recarregar a página\n"
        "- **💬 Perguntar** — clique no botão ao lado de qualquer documento e o nome é "
        "preenchido automaticamente no campo de chat para você refinar a pergunta\n\n"
        "---\n\n"
        "## 📎 Enviar documentos\n\n"
        "Clique no **ícone de anexo (📎)** no chat para enviar PDFs, planilhas ou imagens. "
        "O arquivo entra na fila de análise técnica antes de ser integrado à biblioteca.\n\n"
        "**Boas práticas:**\n\n"
        "1. **Leia antes de subir** — arquivo muito narrativo? Extraia só a parte relevante num `.txt`\n"
        "2. **Um assunto por arquivo** — documentos misturados aumentam o ruído nas buscas\n"
        "3. **Valide depois** — pergunte algo que o documento deveria responder e confirme "
        "que a **Verificação** transcreve o trecho correto\n"
        "4. **Se ainda falhar** → use o 👎 para sinalizar ao time técnico\n\n"
        "---\n\n"
        "## 💡 Nova Ideia\n\n"
        "Clique em **💡 Nova Ideia** na barra lateral para abrir o formulário inline "
        "(sem sair da página de chat).\n\n"
        "Use para registrar orientações internas, procedimentos ou correções de processo. "
        "Sua ideia passa por aprovação antes de ser ativada e começa a influenciar as respostas.\n\n"
        "---\n\n"
        "## 👍👎 Feedback\n\n"
        "| Ícone | Quando usar | O que acontece |\n"
        "|---|---|---|\n"
        "| 👍 | Resposta útil e precisa | Registra satisfação |\n"
        "| 👎 | Resposta incorreta ou imprecisa | Time técnico analisa e grava correção permanente |\n\n"
        "O 👎 é a ferramenta mais poderosa para melhorar a Digiana — use sempre que ela errar.\n\n"
        "---\n\n"
        "## 🔧 Comandos do chat\n\n"
        "| Comando | O que faz |\n"
        "|---|---|\n"
        "| `/manual` | Exibe este guia novamente |\n"
        "| `/lista` | Mostra seus documentos e ideias enviados com o status de cada um |\n\n"
        "---\n\n"
        "## 🚫 Fora do escopo\n\n"
        "- Política, esportes, culinária, turismo, entretenimento\n"
        "- Consultas que exijam responsabilidade técnica formal de contador\n"
        "- Dados não disponíveis na biblioteca *(a Digiana indica a fonte oficial, não inventa)*\n\n"
        "---\n\n"
        "*Pronto — é só perguntar. Use `/manual` a qualquer momento para voltar aqui.*"
    )


def _manual_superusuario(nome):
    return (
        f"# 📖 Guia Completo da Digiana\n\n"
        f"Olá, **{nome}**! Manual de uso, administração e melhores práticas.\n\n"
        "---\n\n"
        "## ⚡ Uso rápido\n\n"
        "Perguntas contábeis e fiscais em linguagem natural — seja específico:\n\n"
        "> *\"Qual a alíquota do DAS para MEI em 2024?\"*\n"
        "> *\"Quais são as obrigações acessórias do Simples Nacional?\"*\n"
        "> *\"Qual o prazo de entrega da ECD para o exercício 2024?\"*\n\n"
        "**Respostas sempre no formato:**\n\n"
        "| Bloco | Conteúdo |\n"
        "|---|---|\n"
        "| **Verificação** | Trecho literal do documento que responde a pergunta |\n"
        "| **Resposta** | Baseada *exclusivamente* na Verificação — nunca inventa dados |\n\n"
        "**Feedback** → 👍 confirma precisão · 👎 abre ciclo de correção RLHF\n\n"
        "**Documentos** → ícone 📎 no chat envia para a Biblioteca como pendente de auditoria\n\n"
        "**Boas práticas ao enviar documentos:**\n\n"
        "1. **Leia antes de subir** — arquivo narrativo? Extraia só a parte relevante num `.txt`\n"
        "2. **Um assunto por arquivo** — documentos misturados aumentam o ruído semântico\n"
        "3. **Valide depois** — pergunte algo que o documento deveria responder e confirme "
        "que a **Verificação** transcreve o trecho certo; se vier vazia, revise ou divida no painel\n"
        "4. **Se ainda alucinar** → registre via 👎 para fechar o ciclo RLHF\n\n"
        "**Comandos do chat:**\n\n"
        "| Comando | O que faz |\n"
        "|---|---|\n"
        "| `/manual` | Exibe este guia novamente |\n"
        "| `/lista` | Mostra documentos e ideias enviados com status de cada um |\n\n"
        "---\n\n"
        "## 📚 Biblioteca (modal SPA)\n\n"
        "Clique em **📚 Biblioteca** na barra lateral — abre sem recarregar a página.\n\n"
        "- **Busca instantânea** — filtre pelo nome do arquivo em tempo real\n"
        "- **💬 Perguntar** — preenche automaticamente o campo de chat com o nome do documento\n"
        "- **⚙️ Administrar** — atalho direto para o painel de gestão da biblioteca\n\n"
        "---\n\n"
        "## 💡 Nova Ideia (modal inline)\n\n"
        "Clique em **💡 Nova Ideia** na barra lateral — formulário abre sem sair do chat.\n"
        "Ideias de superusuários são ativadas automaticamente. "
        "Ideias de usuários comuns passam por aprovação.\n\n"
        "---\n\n"
        "## 🧠 Como a Digiana aprende — 3 Pilares\n\n"
        "**📚 1. Biblioteca de Curadoria**\n"
        "Documentos aprovados (PDF, DOCX, XLSX, imagens) são vetorizados no ChromaDB com embeddings multilíngues.\n"
        "A busca semântica recupera os trechos mais relevantes para cada pergunta.\n\n"
        "Maior impacto: **tabelas de alíquotas com datas**, **calendários de obrigações**, "
        "**legislação consolidada com artigos numerados**, **encargos por faixa**.\n\n"
        "Evite: PDFs longos e narrativos sem dados estruturados, documentos duplicados ou desatualizados.\n\n"
        "**💡 2. Banco de Ideias**\n"
        "Orientações e procedimentos internos injetados como contexto nas perguntas relacionadas.\n"
        "São recuperados por **busca por palavra-chave**: o título e conteúdo precisam "
        "conter os termos que os usuários vão digitar.\n\n"
        "**🔁 3. RLHF — Aprendizado por Correção**\n"
        "Um 👎 abre o ciclo: você grava a resposta ideal no painel → ela é vetorizada "
        "com o par pergunta/resposta-ideal → passa a corrigir respostas similares futuras "
        "**de forma permanente, sem alterar pesos do modelo**.\n\n"
        "---\n\n"
        "## ⚙️ Painel Administrativo\n\n"
        "### 📊 Dashboard — `/admin-panel/`\n"
        "Métricas em tempo real via SSE (sem recarregar):\n"
        "- Usuários online, sessões abertas no dia, total de 👍 e 👎\n"
        "- Atalhos rápidos para todas as seções do painel\n\n"
        "### 📚 Biblioteca — `/admin-panel/biblioteca/`\n"
        "**Upload direto (superusuário):**\n"
        "- Envie PDF, DOCX, XLSX ou imagens — aprovado e vetorizado no ChromaDB no mesmo ato\n"
        "- Suporte a upload em lote (múltiplos arquivos simultâneos)\n\n"
        "**Auditoria de pendentes (enviados pelos usuários via 📎):**\n"
        "- Visualize e edite o texto extraído antes de aprovar\n"
        "- **Aprovar** → vetoriza e entra imediatamente nas respostas\n"
        "- **Rejeitar** → registre o motivo; histórico preservado\n\n"
        "### 💡 Ideias — `/admin-panel/ideias/`\n"
        "- **Criar** → nasce ativa automaticamente\n"
        "- **Ativar/Desativar** → controla se entra no contexto das respostas\n"
        "- **Editar** → conteúdo atualizado entra nas próximas perguntas relacionadas\n"
        "- **Excluir** → remove do banco e do vector store\n\n"
        "### 🔁 Feedback RLHF — `/admin-panel/feedback/dislike/`\n"
        "- Lista de 👎 agrupada por usuário e quantidade\n"
        "- Abra cada item: veja pergunta original + resposta incorreta da IA\n"
        "- **Grave a resposta ideal** → vetorizada com o par pergunta/resposta\n"
        "- Perguntas similares futuras recebem a correção como contexto — **permanente**\n\n"
        "*Priorize: IA inventou valores, alíquotas ou artigos inexistentes.*\n\n"
        "### 👥 Usuários — `/admin-panel/usuarios/`\n"
        "- **Criar** → e-mail `@anagma.com.br` ativa acesso automaticamente\n"
        "- **Status:** Ativo · Inativo · Pausado *(mantém histórico, bloqueia login)*\n"
        "- **Nível:** usuário comum ou superusuário\n"
        "- **Redefinir senha** → troca obrigatória no próximo acesso\n"
        "- **Excluir com histórico** → preserva conversas para treinamento futuro\n"
        "- **Purga total** → remove usuário e todos os dados permanentemente\n\n"
        "### 📈 Insights — `/admin-panel/insights/`\n"
        "- Interações **por hora** (hoje) e **por dia** (últimos 7 dias)\n"
        "- Identifica horários de pico e dimensiona disponibilidade do servidor\n\n"
        "### 🤖 Modelos — `/admin-panel/modelos/`\n"
        "- **Modelo Leve** (GGUF Q4_K_M) — menor RAM, resposta mais rápida\n"
        "- **Modelo Completo** (Safetensors) — maior precisão, maior consumo\n"
        "- Troca sem reiniciar o servidor; status em tempo real: `PRONTO` · `CARREGANDO` · `ERRO`\n\n"
        "### 🧑 Perfil Anagma — `/admin-panel/perfil/`\n"
        "Texto institucional injetado como contexto em todas as respostas da Digiana.\n"
        "Use para definir o tom, escopo e identidade da IA.\n\n"
        "---\n\n"
        "*Regra de ouro: quanto mais documentos específicos e estruturados na biblioteca, "
        "menor a chance de alucinação. Use `/manual` a qualquer momento para voltar aqui.*"
    )


def _group_sessions(sessions):
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    last_7 = today - timedelta(days=7)
    last_30 = today - timedelta(days=30)

    order = ['Fixadas', 'Hoje', 'Ontem', 'Últimos 7 dias', 'Últimos 30 dias', 'Anteriores']
    groups = {g: [] for g in order}

    for s in sessions:
        if s.pinned:
            groups['Fixadas'].append(s)
            continue
        d = timezone.localtime(s.atualizado_em).date()
        if d == today:
            groups['Hoje'].append(s)
        elif d == yesterday:
            groups['Ontem'].append(s)
        elif d >= last_7:
            groups['Últimos 7 dias'].append(s)
        elif d >= last_30:
            groups['Últimos 30 dias'].append(s)
        else:
            groups['Anteriores'].append(s)

    return [(label, slist) for label, slist in groups.items() if slist]


@never_cache
@login_required
def chat_home(request):
    sessions = ChatSession.objects.filter(user=request.user, deleted_at__isnull=True)
    context = {
        'grouped_sessions': _group_sessions(sessions),
        'current_session': None,
        'messages_json': None,
        'saudacao': _get_saudacao(),
        'nome_usuario': request.user.nome_completo or request.user.username,
    }
    return render(request, 'chat/home.html', context)


from django.http import StreamingHttpResponse

@login_required
def chat_stream(request):
    """
    Endpoint de Streaming SSE para o chat.
    Recebe message e session_id via GET.
    """
    user_prompt = request.GET.get('message', '').strip()
    session_id = request.GET.get('session_id')
    
    if not user_prompt:
        return JsonResponse({'status': 'error', 'message': 'Mensagem vazia'}, status=400)

    def event_stream():
        llm_engine = get_llm_engine()
        session = None
        if session_id:
            session = ChatSession.objects.filter(id=session_id, user=request.user, deleted_at__isnull=True).first()

        if not session:
            titulo = user_prompt[:50] + ('...' if len(user_prompt) > 50 else '')
            session = ChatSession.objects.create(user=request.user, titulo=titulo)

        # Registra pergunta do usuário se for nova sessão ou última msg não for essa
        ultima_msg = session.messages.order_by('-timestamp').first()
        if not ultima_msg or ultima_msg.content != user_prompt:
            ChatMessage.objects.create(session=session, role='user', content=user_prompt)

        yield f"event: session_id\ndata: {session.id}\n\n"

        # Intercepta comando /manual antes de acionar o LLM
        if user_prompt.strip().lower().startswith('/manual'):
            user_name = request.user.nome_completo or request.user.username
            if request.user.is_superuser:
                resposta_manual = _manual_superusuario(user_name)
            else:
                resposta_manual = _manual_usuario(user_name)
            # SSE não suporta \n dentro de um data: — cada \n deve virar \ndata:
            resposta_sse = resposta_manual.replace('\n', '\ndata: ')
            yield f"data: {resposta_sse}\n\n"
            ChatMessage.objects.create(session=session, role='assistant', content=resposta_manual)
            session.save()
            return

        history_msgs = session.messages.order_by('timestamp')
        chat_history = [{'role': m.role, 'content': m.content} for m in history_msgs]

        user_name = request.user.nome_completo or request.user.username
        saudacao = _get_saudacao()

        # Solução B — Interceptor de continuação de Excel
        search_query = user_prompt
        excel_continuacao = _detectar_excel_continuacao(session, user_prompt)
        if excel_continuacao:
            search_query = excel_continuacao
            print(f"[EXCEL CONTINUAÇÃO] Rebuscando arquivo: {excel_continuacao}", flush=True)

        full_response = ""

        for token in llm_engine.gerar_resposta_stream(
            user_query=user_prompt,
            chat_history=chat_history,
            user_name=user_name,
            saudacao=saudacao,
            search_query=search_query,
            user=request.user
        ):
            full_response += token
            safe_token = token.replace('\n', '\ndata: ')
            yield f"data: {safe_token}\n\n"

        # Solução C — Aviso de exibição parcial de planilha
        aviso = _verificar_truncamento_excel(search_query, full_response, request.user)
        if aviso:
            full_response += aviso
            safe_aviso = aviso.replace('\n', '\ndata: ')
            yield f"data: {safe_aviso}\n\n"

        # Salva a resposta completa no banco ao final e devolve o ID via SSE
        if full_response:
            ai_msg = ChatMessage.objects.create(session=session, role='assistant', content=full_response)
            session.save()
            yield f"event: message_id\ndata: {ai_msg.id}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # Importante para Nginx não fazer buffer do stream
    return response

@login_required
def send_message(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método inválido'}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido'}, status=400)

    user_prompt = data.get('message', '').strip()
    session_id = data.get('session_id')

    if not user_prompt:
        return JsonResponse({'status': 'error', 'message': 'Mensagem vazia'}, status=400)

    is_new = not bool(session_id)

    try:
        if session_id:
            session = ChatSession.objects.get(id=session_id, user=request.user, deleted_at__isnull=True)
        else:
            titulo = user_prompt[:50] + ('...' if len(user_prompt) > 50 else '')
            session = ChatSession.objects.create(user=request.user, titulo=titulo)
    except ChatSession.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Sessão não encontrada'}, status=404)

    history_msgs = session.messages.order_by('timestamp')
    chat_history = [{'role': m.role, 'content': m.content} for m in history_msgs]

    ChatMessage.objects.create(session=session, role='user', content=user_prompt)

    user_name = request.user.nome_completo or request.user.username
    saudacao = _get_saudacao()

    # Intercepta comando /manual antes de acionar o LLM
    if user_prompt.strip().lower().startswith('/manual'):
        if request.user.is_superuser:
            ai_response = _manual_superusuario(user_name)
        else:
            ai_response = _manual_usuario(user_name)
        ai_msg = ChatMessage.objects.create(session=session, role='assistant', content=ai_response)
        session.save()
        return JsonResponse({
            'status': 'success',
            'session_id': session.id,
            'session_title': session.titulo,
            'is_new': is_new,
            'response': ai_response,
            'message_id': ai_msg.id,
            'time': timezone.localtime().strftime('%H:%M'),
        })

    try:
        llm_engine = get_llm_engine()
        # Solução B — Interceptor de continuação de Excel (caminho não-streaming)
        search_query = user_prompt
        excel_continuacao = _detectar_excel_continuacao(session, user_prompt)
        if excel_continuacao:
            search_query = excel_continuacao
            print(f"[EXCEL CONTINUAÇÃO] Rebuscando arquivo: {excel_continuacao}", flush=True)
        ai_response = llm_engine.gerar_resposta(
            user_query=user_prompt,
            chat_history=chat_history,
            user_name=user_name,
            saudacao=saudacao,
            search_query=search_query,
            user=request.user
        )
    except Exception:
        import traceback
        traceback.print_exc()
        ai_response = 'Desculpe, ocorreu um erro interno ao processar sua mensagem. Tente novamente.'

    ai_msg = ChatMessage.objects.create(session=session, role='assistant', content=ai_response)
    session.save()

    return JsonResponse({
        'status': 'success',
        'session_id': session.id,
        'session_title': session.titulo,
        'is_new': is_new,
        'response': ai_response,
        'message_id': ai_msg.id,
        'time': timezone.localtime().strftime('%H:%M'),
    })


@never_cache
@login_required
def chat_session(request, session_id):
    session = get_object_or_404(ChatSession, id=session_id, user=request.user, deleted_at__isnull=True)
    sessions = ChatSession.objects.filter(user=request.user, deleted_at__isnull=True)

    messages_data = []
    for m in session.messages.order_by('timestamp'):
        status_anexo = None
        nome_arquivo = None
        
        if m.content.startswith('[Anexo enviado:') and ']' in m.content:
            try:
                nome_arquivo = m.content.split('[Anexo enviado: ')[1].split(']')[0]
                doc = DocumentoBiblioteca.objects.filter(nome_arquivo=nome_arquivo).first()
                if doc:
                    status_anexo = doc.status
            except Exception:
                pass

        messages_data.append({
            'id': m.id,
            'role': m.role,
            'content': m.content,
            'time': timezone.localtime(m.timestamp).strftime('%H:%M'),
            'feedback': m.feedback,
            'status_anexo': status_anexo,
            'nome_arquivo': nome_arquivo
        })

    context = {
        'grouped_sessions': _group_sessions(sessions),
        'current_session': session,
        'messages_json': messages_data,
        'saudacao': _get_saudacao(),
        'nome_usuario': request.user.nome_completo or request.user.username,
    }
    return render(request, 'chat/home.html', context)


@login_required
def rename_session(request, session_id):
    session = get_object_or_404(ChatSession, id=session_id, user=request.user)
    try:
        data = json.loads(request.body)
        titulo = data.get('titulo', '').strip()
        if titulo:
            session.titulo = titulo[:255]
            session.save(update_fields=['titulo'])
            return JsonResponse({'status': 'success', 'titulo': session.titulo})
    except Exception:
        pass
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def pin_session(request, session_id):
    session = get_object_or_404(ChatSession, id=session_id, user=request.user)
    session.pinned = not session.pinned
    session.save(update_fields=['pinned'])
    return JsonResponse({'status': 'success', 'pinned': session.pinned})


@login_required
def get_session_messages(request, session_id):
    """Retorna as mensagens de uma sessão em JSON para navegação SPA."""
    session = get_object_or_404(ChatSession, id=session_id, user=request.user, deleted_at__isnull=True)
    messages_data = []
    for m in session.messages.order_by('timestamp'):
        status_anexo = None
        nome_arquivo = None
        if m.content.startswith('[Anexo enviado:') and ']' in m.content:
            try:
                nome_arquivo = m.content.split('[Anexo enviado: ')[1].split(']')[0]
                doc = DocumentoBiblioteca.objects.filter(nome_arquivo=nome_arquivo).first()
                if doc: status_anexo = doc.status
            except: pass

        messages_data.append({
            'id': m.id,
            'role': m.role,
            'content': m.content,
            'time': timezone.localtime(m.timestamp).strftime('%H:%M'),
            'feedback': m.feedback,
            'status_anexo': status_anexo,
            'nome_arquivo': nome_arquivo
        })
    return JsonResponse({
        'status': 'success',
        'session_id': session.id,
        'session_title': session.titulo,
        'messages': messages_data
    })


@login_required
def message_feedback(request, message_id):
    msg = get_object_or_404(ChatMessage, id=message_id, role='assistant', session__user=request.user)
    try:
        data = json.loads(request.body)
        feedback = data.get('feedback')
        msg.feedback = None if msg.feedback == feedback else feedback
        msg.save(update_fields=['feedback'])
        return JsonResponse({'status': 'success', 'feedback': msg.feedback})
    except Exception:
        pass
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def delete_session(request, session_id):
    session = get_object_or_404(ChatSession, id=session_id, user=request.user, deleted_at__isnull=True)
    session.deleted_at = timezone.now()
    session.deleted_by = request.user
    session.save(update_fields=['deleted_at', 'deleted_by'])
    return JsonResponse({'status': 'success'})


@login_required
def meus_envios(request):
    from core.models import GlobalIdeia

    docs = DocumentoBiblioteca.objects.filter(
        enviado_por=request.user
    ).order_by('-criado_em').values('nome_arquivo', 'status', 'criado_em')

    ideias = GlobalIdeia.objects.filter(
        autor=request.user
    ).order_by('-criado_em').values('titulo', 'ativa', 'criado_em')

    return JsonResponse({
        'status': 'success',
        'documentos': [
            {
                'nome': d['nome_arquivo'],
                'status': d['status'],
                'criado_em': d['criado_em'].strftime('%d/%m/%Y'),
            }
            for d in docs
        ],
        'ideias': [
            {
                'titulo': i['titulo'],
                'ativa': i['ativa'],
                'criado_em': i['criado_em'].strftime('%d/%m/%Y'),
            }
            for i in ideias
        ],
    })
