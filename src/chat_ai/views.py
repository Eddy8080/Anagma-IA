from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.cache import cache
from django.utils import timezone
from django.utils.html import strip_tags
from datetime import timedelta
from .models import ChatSession, ChatMessage
from django.views.decorators.http import require_POST
from .llm_engine import AnagmaLLMEngine
import json

_llm_engine = None


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
    """Retorna GlobalIdeias ativas com cache de 5 minutos. Strip de HTML antes de alimentar o LLM."""
    ideias = cache.get('global_ideias')
    if ideias is None:
        from core.models import GlobalIdeia
        qs = GlobalIdeia.objects.filter(ativa=True).values('titulo', 'conteudo').order_by('criado_em')
        ideias = [{'titulo': i['titulo'], 'conteudo': strip_tags(i['conteudo'])} for i in qs]
        cache.set('global_ideias', ideias, timeout=300)
    return ideias


def _group_sessions(sessions):
    """Agrupa sessões por faixas de tempo. Fixadas aparecem primeiro."""
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


@login_required
def chat_home(request):
    sessions = ChatSession.objects.filter(user=request.user)
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
            session = ChatSession.objects.get(id=session_id, user=request.user)
        else:
            titulo = user_prompt[:50] + ('...' if len(user_prompt) > 50 else '')
            session = ChatSession.objects.create(user=request.user, titulo=titulo)
    except ChatSession.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Sessão não encontrada'}, status=404)

    # Captura histórico ANTES de salvar a mensagem atual
    history_msgs = session.messages.order_by('timestamp')
    chat_history = [{'role': m.role, 'content': m.content} for m in history_msgs]

    ChatMessage.objects.create(session=session, role='user', content=user_prompt)

    user_name = request.user.nome_completo or request.user.username
    saudacao = _get_saudacao()
    ideias = _get_ideias_ativas()

    try:
        llm_engine = get_llm_engine()
        ai_response = llm_engine.gerar_resposta(
            user_query=user_prompt,
            chat_history=chat_history,
            user_name=user_name,
            saudacao=saudacao,
            ideias=ideias,
        )
    except Exception:
        import traceback
        traceback.print_exc()
        ai_response = 'Desculpe, ocorreu um erro interno ao processar sua mensagem. Tente novamente.'

    ai_msg = ChatMessage.objects.create(session=session, role='assistant', content=ai_response)

    # Atualiza atualizado_em para manter ordenação correta na sidebar
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


@login_required
def chat_session(request, session_id):
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
    except ChatSession.DoesNotExist:
        return redirect('chat:home')

    sessions = ChatSession.objects.filter(user=request.user)

    messages_data = [
        {
            'id': m.id,
            'role': m.role,
            'content': m.content,
            'time': timezone.localtime(m.timestamp).strftime('%H:%M'),
            'feedback': m.feedback,
        }
        for m in session.messages.order_by('timestamp')
    ]

    context = {
        'grouped_sessions': _group_sessions(sessions),
        'current_session': session,
        'messages_json': messages_data,   # lista Python — json_script serializa no template
        'saudacao': _get_saudacao(),
        'nome_usuario': request.user.nome_completo or request.user.username,
    }
    return render(request, 'chat/home.html', context)


@login_required
def rename_session(request, session_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=400)
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
    except ChatSession.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Sessão não encontrada'}, status=404)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error'}, status=400)
    titulo = data.get('titulo', '').strip()
    if not titulo:
        return JsonResponse({'status': 'error', 'message': 'Título vazio'}, status=400)
    session.titulo = titulo[:255]
    session.save(update_fields=['titulo'])
    return JsonResponse({'status': 'success', 'titulo': session.titulo})


@login_required
def pin_session(request, session_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=400)
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
    except ChatSession.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Sessão não encontrada'}, status=404)
    session.pinned = not session.pinned
    session.save(update_fields=['pinned'])
    return JsonResponse({'status': 'success', 'pinned': session.pinned})


@login_required
def message_feedback(request, message_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=400)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error'}, status=400)

    feedback = data.get('feedback')
    if feedback not in ('like', 'dislike', None):
        return JsonResponse({'status': 'error', 'message': 'Feedback inválido'}, status=400)

    try:
        msg = ChatMessage.objects.get(id=message_id, role='assistant', session__user=request.user)
    except ChatMessage.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Mensagem não encontrada'}, status=404)

    # Toggle: clicar no mesmo valor limpa (None)
    msg.feedback = None if msg.feedback == feedback else feedback
    msg.save(update_fields=['feedback'])
    return JsonResponse({'status': 'success', 'feedback': msg.feedback})


@login_required
def delete_session(request, session_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=400)
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
    except ChatSession.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Sessão não encontrada'}, status=404)
    session.delete()
    return JsonResponse({'status': 'success'})
