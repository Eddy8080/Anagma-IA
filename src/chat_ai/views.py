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

_llm_engine = None

@login_required
@require_POST
def upload_document(request):
    """
    Recebe um arquivo, extrai texto via OCR e salva na Biblioteca para auditoria.
    Retorna a resposta padrão da IA confirmando o recebimento.
    """
    if 'file' not in request.FILES:
        return JsonResponse({'status': 'error', 'message': 'Nenhum arquivo enviado'}, status=400)

    uploaded_file = request.FILES['file']
    session_id = request.POST.get('session_id')
    nome_original = uploaded_file.name
    ext = nome_original.split('.')[-1].lower() if '.' in nome_original else ''

    if ext not in ['pdf', 'png', 'jpg', 'jpeg']:
        return JsonResponse({'status': 'error', 'message': 'Extensão não suportada'}, status=400)

    try:
        # 1. Salva na Biblioteca (Mantendo a Governança de Autoria)
        doc_bib = DocumentoBiblioteca.objects.create(
            nome_arquivo=nome_original,
            arquivo=uploaded_file,
            extensao=ext,
            status='pending',
            enviado_por=request.user
        )

        # 2. Extrai texto (com limite de 10 páginas embutido no processador)
        doc_bib.arquivo.open('rb')
        try:
            texto_extraido = AnagmaDocumentProcessor.extrair_texto(doc_bib.arquivo, ext)
        finally:
            doc_bib.arquivo.close()
        doc_bib.conteudo_extraido = texto_extraido
        doc_bib.processado_em = timezone.now()
        doc_bib.save(update_fields=['conteudo_extraido', 'processado_em'])

        # 3. Gerenciar Sessão de Chat
        if session_id:
            try:
                session = ChatSession.objects.get(id=session_id, user=request.user)
            except ChatSession.DoesNotExist:
                session = ChatSession.objects.create(user=request.user, titulo=f"Anexo: {nome_original}")
        else:
            session = ChatSession.objects.create(user=request.user, titulo=f"Anexo: {nome_original}")

        # 4. Registra no Chat (Mensagem do Usuário)
        ChatMessage.objects.create(session=session, role='user', content=f"[Anexo enviado: {nome_original}]")

        # 5. Resposta Padrão da IA (UX)
        trecho = (texto_extraido[:300].replace('\n', ' ') if texto_extraido else "Conteúdo técnico em análise")
        ai_response = (
            f"Recebi o documento **{nome_original}**. "
            f"Identifiquei preliminarmente que ele contém informações sobre: *{trecho}...* "
            f"\n\nO conteúdo já foi encaminhado para a nossa **Biblioteca de Curadoria** e está em **processo de auditoria** "
            f"pelos superusuários para garantir a precisão técnica antes de ser integrado definitivamente ao meu aprendizado contábil."
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
        import traceback
        traceback.print_exc()
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

    try:
        llm_engine = get_llm_engine()
        # A busca deve focar apenas no prompt atual para ser precisa.
        # Adicionar o título da sessão pode causar ruído e impedir que o RAG encontre documentos exatos.
        ai_response = llm_engine.gerar_resposta(
            user_query=user_prompt,
            chat_history=chat_history,
            user_name=user_name,
            saudacao=saudacao,
            search_query=user_prompt,
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
