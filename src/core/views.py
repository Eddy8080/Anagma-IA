from django.shortcuts import render, redirect, get_object_or_404
from django.db import models
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from .forms import CustomUserRegistrationForm
from .decorators import superuser_required
from django.http import JsonResponse
from .models import GlobalIdeia, CustomUser, PerfilAnagma, ConfiguracaoIA
from chat_ai.llm_engine import AnagmaLLMEngine
import threading
import json
import time

@superuser_required
def admin_modelos(request):
    config = ConfiguracaoIA.get_solo()
    
    if request.method == 'POST':
        novo_modelo = request.POST.get('modelo')
        if novo_modelo in ['LEVE', 'COMPLETO']:
            config.modelo_preferido = novo_modelo
            config.status = 'CARREGANDO'
            config.progresso = 0
            config.etapa_nome = "Iniciando solicitação de troca..."
            config.save()
            
            # Dispara a troca em uma thread separada para não travar o request
            def task_recarregar():
                engine = AnagmaLLMEngine()
                engine.recarregar_modelo()
            
            thread = threading.Thread(target=task_recarregar)
            thread.start()
            
            return JsonResponse({'status': 'ok'})

    return render(request, 'admin_panel/modelos.html', {
        'config': config,
        'segment': 'modelos'
    })

@superuser_required
def admin_ia_status(request):
    """Endpoint para o JavaScript consultar o progresso do carregamento."""
    config = ConfiguracaoIA.get_solo()
    return JsonResponse({
        'status': config.status,
        'modelo_em_uso': config.get_modelo_em_uso_display(),
        'etapa': config.etapa_nome,
        'progresso': config.progresso,
        'erro': config.ultimo_erro if config.status == 'ERRO' else None
    })
from .decorators import superuser_required
from chat_ai.vocabulario import TERMOS_CONTABEIS

class AnagmaLoginView(LoginView):
    """
    View de login customizada para suportar a funcionalidade 'Lembrar-me'.
    Usuário já autenticado (lembrar-me ativo) é redirecionado direto para o chat.
    """
    template_name = 'registration/login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        remember_me = self.request.POST.get('remember_me')
        user = form.get_user()
        auth_login(self.request, user)
        
        if remember_me:
            # Mantém logado por 30 dias
            self.request.session.set_expiry(2592000)
        else:
            # Expira ao fechar o navegador
            self.request.session.set_expiry(0)
            
        # Verificação de Troca de Senha Obrigatória
        if user.password_change_required:
            return redirect('force_password_change')
            
        return redirect(self.get_success_url())

@require_POST
def logout_view(request):
    """
    Garante o encerramento da sessão e redireciona para o login.
    Requer POST para evitar logout por CSRF via GET.
    """
    auth_logout(request)
    return redirect('login')

def register_view(request):
    if request.method == 'POST':
        form = CustomUserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Conta criada com sucesso! Faça o login.")
            return redirect('login')
    else:
        form = CustomUserRegistrationForm()

    return render(request, 'registration/register.html', {'form': form})


def _eh_ideia_contabil(titulo, conteudo):
    """Retorna True se o texto contém ao menos um termo do domínio contábil."""
    texto = f' {titulo} {conteudo} '.lower()
    return any(termo in texto for termo in TERMOS_CONTABEIS)


@login_required
def biblioteca_catalogo(request):
    """
    Catálogo público de documentos aprovados na biblioteca da Digiana.
    Suporta AJAX (X-Requested-With: XMLHttpRequest) retornando JSON para o modal SPA.
    """
    from .models import DocumentoBiblioteca
    qs = (
        DocumentoBiblioteca.objects
        .filter(status='approved')
        .order_by('-processado_em')
    )
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        docs = [
            {
                'id': d.id,
                'nome_arquivo': d.nome_arquivo,
                'extensao': d.extensao,
                'precisa_revisao': d.precisa_revisao,
                'processado_em': timezone.localtime(d.processado_em).strftime('%d/%m/%Y') if d.processado_em else '',
            }
            for d in qs
        ]
        return JsonResponse({'documentos': docs, 'is_superuser': request.user.is_superuser})
    return render(request, 'biblioteca/catalogo.html', {
        'documentos': qs,
        'is_superuser': request.user.is_superuser,
    })


@login_required
def criar_ideia(request):
    if request.method == 'POST':
        titulo   = request.POST.get('titulo', '').strip()
        conteudo = request.POST.get('conteudo', '').strip()
        is_ajax  = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if not titulo or not conteudo:
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': 'Preencha título e conteúdo.'}, status=400)
            messages.error(request, 'Preencha título e conteúdo.')
            return render(request, 'core/criar_ideia.html')

        GlobalIdeia.objects.create(
            autor=request.user,
            titulo=titulo,
            conteudo=conteudo,
            ativa=False,
        )
        msg = 'Sua ideia foi enviada para análise técnica e estará disponível em breve.'
        if is_ajax:
            return JsonResponse({'status': 'success', 'message': msg})
        messages.success(request, msg)
        return redirect('chat:home')

    return render(request, 'core/criar_ideia.html')


# ---------------------------------------------------------------------------
# Painel de superusuários
# ---------------------------------------------------------------------------

def _get_dashboard_stats():
    from chat_ai.models import ChatSession, ChatMessage
    from django.db import connection
    from django.db.models import Q
    from django.contrib.sessions.models import Session
    from datetime import timedelta
    # Força a limpeza de cache de query para esta thread de stream
    connection.close() 
    
    agora = timezone.now()
    hoje = agora.date()
    ontem = hoje - timedelta(days=1)
    
    # 1. Usuários Online: Baseado em Sessões Não Expiradas e Ativas
    sessions = Session.objects.filter(expire_date__gte=agora)
    online_ids = []
    for session in sessions:
        data = session.get_decoded()
        uid = data.get('_auth_user_id')
        if uid:
            online_ids.append(uid)
    
    # Remove duplicados (um usuário pode ter mais de uma sessão aberta)
    total_online = len(set(online_ids))

    # 2. Usuários Ativos Ontem: Interagiram com o sistema no dia anterior
    users_ontem_ids = CustomUser.objects.filter(
        Q(last_login__date=ontem) |
        Q(sessions__messages__timestamp__date=ontem)
    ).values_list('id', flat=True).distinct()
    
    return {
        'total_usuarios': CustomUser.objects.count(),
        'total_ideias_ativas': GlobalIdeia.objects.filter(ativa=True).count(),
        'sessoes_hoje': ChatSession.objects.filter(criado_em__date=hoje).count(),
        'total_likes': ChatMessage.objects.filter(feedback='like', session__isnull=False, session__deleted_at__isnull=True).count(),
        'total_dislikes': ChatMessage.objects.filter(feedback='dislike', session__isnull=False, session__deleted_at__isnull=True).count(),
        # Métricas de Atividade Real
        'usuarios_online': total_online,
        'usuarios_ontem': len(users_ontem_ids),
    }

@superuser_required
def admin_panel(request):
    return render(request, 'admin_panel/dashboard.html', _get_dashboard_stats())

@superuser_required
def admin_dashboard_stats(request):
    return JsonResponse(_get_dashboard_stats())

@superuser_required
def admin_dashboard_stream(request):
    import json, time
    from django.http import StreamingHttpResponse

    def event_stream():
        last = {}
        while True:
            stats = _get_dashboard_stats()
            if stats != last:
                last = stats
                yield f"data: {json.dumps(stats)}\n\n"
            time.sleep(3)

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@superuser_required
def admin_ideias_stream(request):
    import json, time
    from django.http import StreamingHttpResponse

    def event_stream():
        last_count = GlobalIdeia.objects.count()
        while True:
            # Verifica se houve nova ideia
            current_count = GlobalIdeia.objects.count()
            if current_count > last_count:
                # Busca as novas ideias criadas desde o último check
                novas = GlobalIdeia.objects.select_related('autor').order_by('-criado_em')[:current_count - last_count]
                for ideia in reversed(novas): # Envia da mais antiga para a mais nova
                    data = {
                        'pk': ideia.pk,
                        'titulo': ideia.titulo,
                        'conteudo': ideia.conteudo,
                        'autor': ideia.autor.username if ideia.autor else "—",
                        'criado_em': timezone.localtime(ideia.criado_em).strftime('%d/%m/%Y %H:%M'),
                        'ativa': ideia.ativa
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                last_count = current_count
            time.sleep(3)

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@superuser_required
def admin_usuarios(request):
    # Ordenação automática definida no Meta do modelo (nome_completo, username)
    usuarios = CustomUser.objects.all()
    return render(request, 'admin_panel/usuarios.html', {'usuarios': usuarios})


@superuser_required
def admin_criar_usuario(request):
    if request.method != 'POST':
        return redirect('admin_panel:usuarios')
    username      = request.POST.get('username', '').strip()
    nome_completo = request.POST.get('nome_completo', '').strip()
    email         = request.POST.get('email', '').strip().lower()
    password      = request.POST.get('password', '').strip()
    status        = request.POST.get('account_status', 'active')

    if not username or not nome_completo or not email or not password:
        messages.error(request, 'Todos os campos são obrigatórios.')
        return redirect('admin_panel:usuarios')
    if CustomUser.objects.filter(username=username).exists():
        messages.error(request, f'Username "{username}" já está em uso.')
        return redirect('admin_panel:usuarios')
    if CustomUser.objects.filter(email=email).exists():
        messages.error(request, f'E-mail "{email}" já está cadastrado.')
        return redirect('admin_panel:usuarios')

    dominio_oficial = email.endswith('@anagma.com.br')
    u = CustomUser.objects.create_user(
        username=username, email=email, password=password,
        nome_completo=nome_completo,
        is_active=(status == 'active' and dominio_oficial),
        account_status=status
    )
    u.password_change_required = True # Novo usuário deve trocar a senha inicial
    u.save()
    if dominio_oficial:
        messages.success(request, f'Usuário "{u.username}" criado com status {u.get_account_status_display()}.')
    else:
        messages.warning(request, f'Usuário "{u.username}" criado como inativo (e-mail fora de @anagma.com.br).')
    return redirect('admin_panel:usuarios')


@superuser_required
def admin_deletar_usuario(request, user_id):
    """
    Deleção inteligente: O Superusuário decide se limpa tudo ou mantém histórico para a IA.
    """
    if request.method == 'POST':
        usuario = get_object_or_404(CustomUser, pk=user_id)
        modo = request.POST.get('modo', 'keep') # 'keep' (preserva histórico) ou 'purge' (limpa tudo)

        if usuario == request.user:
            messages.error(request, 'Você não pode excluir a própria conta.')
            return redirect('admin_panel:usuarios')

        if modo == 'purge':
            # Apaga o usuário e o CASCADE cuidará das mensagens em ChatMessage (mas ChatSession foi alterado para SET_NULL)
            # Para uma purga total real, precisamos apagar as sessões manualmente primeiro
            from chat_ai.models import ChatSession
            ChatSession.objects.filter(user=usuario).delete()
            usuario.delete()
            messages.success(request, f'Usuário {usuario.username} e todos os seus dados foram eliminados permanentemente.')
        else:
            # Apenas apaga o usuário. ChatSession.user e GlobalIdeia.autor ficarão Nulos (SET_NULL)
            usuario.delete()
            messages.success(request, f'Usuário excluído. O histórico e as ideias foram preservados para treinamento da IA.')
            
    return redirect('admin_panel:usuarios')


@superuser_required
def admin_update_user_status(request, user_id):
    """
    Atualiza o status (Ativo, Inativo, Pausado) e o nível de acesso (Superuser).
    """
    if request.method == 'POST':
        usuario = get_object_or_404(CustomUser, pk=user_id)
        if usuario == request.user:
            messages.error(request, 'Você não pode alterar seu próprio status por aqui.')
            return redirect('admin_panel:usuarios')

        novo_status = request.POST.get('status')
        novo_nivel  = request.POST.get('nivel') # 'admin' ou 'user'

        if novo_status in dict(CustomUser.STATUS_CHOICES):
            usuario.account_status = novo_status
            usuario.is_active = (novo_status == 'active')
            
        if novo_nivel in ['admin', 'user']:
            usuario.is_superuser = (novo_nivel == 'admin')
            usuario.is_staff = usuario.is_superuser
            
        usuario.save()
        messages.success(request, f'Perfil de {usuario.username} atualizado.')
        
    return redirect('admin_panel:usuarios')


@superuser_required
def admin_reset_password(request, user_id):
    """
    Permite ao Superusuário redefinir a senha de um usuário específico.
    """
    if request.method == 'POST':
        usuario = get_object_or_404(CustomUser, pk=user_id)
        nova_senha = request.POST.get('nova_senha', '').strip()

        if not nova_senha:
            messages.error(request, 'A nova senha não pode ser vazia.')
            return redirect('admin_panel:usuarios')

        usuario.set_password(nova_senha)
        usuario.password_change_required = True # Obriga a troca no próximo login
        usuario.save()
        messages.success(request, f'Senha de "{usuario.username}" redefinida. O usuário deverá trocá-la no próximo acesso.')
        
    return redirect('admin_panel:usuarios')


@superuser_required
def admin_ideias(request):
    ideias = GlobalIdeia.objects.select_related('autor').order_by('-criado_em')
    ideias_data = [
        {'pk': i.pk, 'titulo': i.titulo, 'conteudo': i.conteudo}
        for i in ideias
    ]
    return render(request, 'admin_panel/ideias.html', {'ideias': ideias, 'ideias_data': ideias_data})


@superuser_required
def admin_criar_ideia(request):
    """
    Permite ao Superusuário adicionar ideias diretamente (já ativas).
    """
    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        conteudo = request.POST.get('conteudo', '').strip()
        if titulo and conteudo:
            GlobalIdeia.objects.create(
                autor=request.user,
                titulo=titulo,
                conteudo=conteudo,
                ativa=True
            )
            messages.success(request, 'Nova ideia adicionada e ativada com sucesso.')
    return redirect('admin_panel:ideias')


@superuser_required
def admin_editar_ideia(request, ideia_id):
    if request.method == 'POST':
        ideia = get_object_or_404(GlobalIdeia, pk=ideia_id)
        titulo = request.POST.get('titulo', '').strip()
        conteudo = request.POST.get('conteudo', '').strip()
        if titulo and conteudo:
            ideia.titulo = titulo
            ideia.conteudo = conteudo
            ideia.save(update_fields=['titulo', 'conteudo'])
            messages.success(request, 'Ideia atualizada com sucesso.')
    return redirect('admin_panel:ideias')


@superuser_required
def admin_deletar_ideia(request, ideia_id):
    if request.method == 'POST':
        ideia = get_object_or_404(GlobalIdeia, pk=ideia_id)
        ideia.delete()
    return redirect('admin_panel:ideias')


@superuser_required
def admin_toggle_ideia(request, ideia_id):
    if request.method == 'POST':
        ideia = get_object_or_404(GlobalIdeia, pk=ideia_id)
        ideia.ativa = not ideia.ativa
        ideia.save()
    return redirect('admin_panel:ideias')


@superuser_required
def admin_perfil_anagma(request):
    from django.core.cache import cache
    perfil = PerfilAnagma.get()
    if request.method == 'POST':
        from django.utils.html import strip_tags
        texto = strip_tags(request.POST.get('texto', '')).strip()
        perfil.texto = texto
        perfil.save()
        cache.delete('perfil_anagma')
        messages.success(request, 'Perfil Anagma atualizado.')
        return redirect('admin_panel:perfil_anagma')
    return render(request, 'admin_panel/perfil_anagma.html', {'perfil': perfil})


@superuser_required
def admin_insights(request):
    """
    Dashboard de estatísticas de engajamento da Digiana IA.
    Agrega dados de interações por hora (hoje) e por dia (últimos 7 dias).
    """
    from chat_ai.models import ChatMessage
    from django.db.models import Count
    from django.db.models.functions import TruncHour, TruncDay
    from datetime import timedelta

    now = timezone.localtime()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_week_start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)

    # 1. Dados Tempo Real (Hoje por hora) - Mensagens dos Usuários
    today_stats = ChatMessage.objects.filter(
        timestamp__gte=today_start,
        role='user'
    ).annotate(
        hour=TruncHour('timestamp')
    ).values('hour').annotate(
        count=Count('id')
    ).order_by('hour')

    # 2. Dados Semanais (Últimos 7 dias)
    weekly_stats = ChatMessage.objects.filter(
        timestamp__gte=last_week_start,
        role='user'
    ).annotate(
        day=TruncDay('timestamp')
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')

    # Preparação para o Chart.js no template
    realtime_labels = [h['hour'].strftime('%H:%M') for h in today_stats]
    realtime_data = [h['count'] for h in today_stats]

    weekly_labels = [d['day'].strftime('%d/%m/%Y') for d in weekly_stats]
    weekly_data = [d['count'] for d in weekly_stats]

    context = {
        'realtime_labels': json.dumps(realtime_labels),
        'realtime_data': json.dumps(realtime_data),
        'weekly_labels': json.dumps(weekly_labels),
        'weekly_data': json.dumps(weekly_data),
        'hoje': now.strftime('%d/%m/%Y'),
    }
    return render(request, 'admin_panel/insights.html', context)


# ---------------------------------------------------------------------------
# Gestão da Biblioteca de Curadoria (Documentos para IA)
# ---------------------------------------------------------------------------

@superuser_required
def admin_biblioteca(request):
    """
    Lista documentos enviados pelos usuários para auditoria.
    """
    from .models import DocumentoBiblioteca
    documentos = DocumentoBiblioteca.objects.all().select_related('auditado_por')
    documentos_com_alerta = documentos.filter(precisa_revisao=True).exists()
    
    return render(request, 'admin_panel/biblioteca.html', {
        'documentos': documentos,
        'documentos_com_alerta': documentos_com_alerta
    })


@superuser_required
def admin_upload_biblioteca(request):
    """
    Permite ao Superusuário subir diversos documentos simultaneamente (já aprovados).
    Usa StreamingHttpResponse para feedback em tempo real no frontend via Fetch/Streams.
    """
    from .models import DocumentoBiblioteca
    from chat_ai.document_processor import AnagmaDocumentProcessor
    from django.http import StreamingHttpResponse

    if request.method != 'POST':
        return redirect('admin_panel:biblioteca')

    files = request.FILES.getlist('arquivo')
    if not files:
        return JsonResponse({'status': 'error', 'message': 'Nenhum arquivo selecionado.'}, status=400)

    def event_stream():
        extensoes_permitidas = ['pdf', 'png', 'jpg', 'jpeg', 'docx', 'doc', 'xlsx', 'xls', 'txt']
        sucessos = 0
        erros = 0
        total = len(files)

        yield json.dumps({'event': 'init', 'total': total}) + "\n"

        for i, uploaded_file in enumerate(files):
            nome_original = uploaded_file.name
            ext = nome_original.split('.')[-1].lower() if '.' in nome_original else ''
            
            yield json.dumps({'event': 'file_start', 'filename': nome_original, 'index': i + 1}) + "\n"

            if ext not in extensoes_permitidas:
                erros += 1
                yield json.dumps({
                    'event': 'file_error', 
                    'filename': nome_original, 
                    'message': 'Extensão não suportada.'
                }) + "\n"
                continue

            try:
                doc = DocumentoBiblioteca.objects.create(
                    nome_arquivo=nome_original,
                    arquivo=uploaded_file,
                    extensao=ext,
                    status='approved',
                    auditado_por=request.user,
                    processado_em=timezone.now()
                )

                import io as _io
                doc.arquivo.open('rb')
                try:
                    file_bytes = doc.arquivo.read()
                finally:
                    doc.arquivo.close()

                texto, meta = AnagmaDocumentProcessor.extrair_texto(_io.BytesIO(file_bytes), ext)
                doc.conteudo_extraido = texto
                doc.save(update_fields=['conteudo_extraido'])

                # Vetoriza no ChromaDB
                if texto and not texto.startswith('Erro'):
                    try:
                        from django.utils.html import strip_tags
                        from chat_ai.llm_engine import AnagmaLLMEngine
                        AnagmaLLMEngine().rag.vetorizar_texto(strip_tags(texto), doc.nome_arquivo)
                    except Exception as e_rag:
                        print(f"[RAG] Erro: {e_rag}")

                # Define mensagem amigável
                msg_amigavel = "Documento integrado com alta precisão."
                status_ui = "success"
                precisa_revisao = False
                
                if meta.get('fallback'):
                    status_ui = "warning"
                    precisa_revisao = True
                    msg_amigavel = (
                        "Estrutura complexa detectada. Adicionado via motor de reserva. "
                        "Recomenda-se salvar como **.docx padrão** ou **.txt** se houver falhas no chat."
                    )
                elif not meta.get('sucesso'):
                    status_ui = "error"
                    precisa_revisao = True
                    msg_amigavel = "Não foi possível extrair o texto. Tente converter para PDF ou TXT."

                if precisa_revisao:
                    doc.precisa_revisao = True
                    doc.save(update_fields=['precisa_revisao'])

                sucessos += 1
                yield json.dumps({
                    'event': 'file_done',
                    'filename': nome_original,
                    'status': status_ui,
                    'message': msg_amigavel,
                    'doc_data': {
                        'id': doc.id,
                        'nome_arquivo': doc.nome_arquivo,
                        'extensao': doc.extensao,
                        'status': doc.status,
                        'precisa_revisao': doc.precisa_revisao,
                        'criado_em': timezone.localtime(doc.criado_em).strftime('%d/%m/%Y %H:%M'),
                        'auditado_por': doc.auditado_por.username if doc.auditado_por else '',
                    }
                }) + "\n"

            except Exception as e:
                erros += 1
                yield json.dumps({
                    'event': 'file_error', 
                    'filename': nome_original, 
                    'message': f'Erro interno: {str(e)}'
                }) + "\n"

        yield json.dumps({'event': 'finish', 'sucessos': sucessos, 'erros': erros}) + "\n"

    response = StreamingHttpResponse(event_stream(), content_type='application/x-ndjson')
    response['X-Accel-Buffering'] = 'no'
    return response


@superuser_required
def admin_documento_conteudo(request, doc_id):
    """Retorna o conteúdo extraído de um documento como JSON (para carregamento sob demanda)."""
    from .models import DocumentoBiblioteca
    doc = get_object_or_404(DocumentoBiblioteca, pk=doc_id)
    return JsonResponse({'content': doc.conteudo_extraido or '', 'nome': doc.nome_arquivo})


@superuser_required
def admin_auditar_documento(request, doc_id):
    """
    Aprova ou Rejeita um documento para a base de conhecimento da IA.
    """
    from .models import DocumentoBiblioteca
    if request.method == 'POST':
        doc = get_object_or_404(DocumentoBiblioteca, pk=doc_id)
        acao = request.POST.get('acao') # 'approve' ou 'reject'
        motivo = request.POST.get('motivo_rejeicao', '').strip()

        if acao == 'approve':
            # Captura o conteúdo editado do editor Quill
            conteudo_editado = request.POST.get('conteudo_editado', '').strip()
            if conteudo_editado:
                doc.conteudo_extraido = conteudo_editado
            
            doc.status = 'approved'
            doc.motivo_rejeicao = ''
            doc.auditado_por = request.user
            doc.processado_em = timezone.now()
            doc.save()

            # Vetoriza no ChromaDB para habilitar busca semântica
            if doc.conteudo_extraido:
                try:
                    from django.utils.html import strip_tags
                    # Remove tags HTML para a vetorização (RAG prefere texto limpo)
                    texto_limpo = strip_tags(doc.conteudo_extraido)
                    
                    from chat_ai.llm_engine import AnagmaLLMEngine
                    AnagmaLLMEngine().rag.vetorizar_texto(texto_limpo, doc.nome_arquivo)
                except Exception as e:
                    print(f"[RAG] Erro ao vetorizar documento aprovado: {e}", flush=True)
            messages.success(request, f'Documento "{doc.nome_arquivo}" aprovado e integrado à base semântica da IA.')
        elif acao == 'reject':
            doc.status = 'rejected'
            doc.motivo_rejeicao = motivo
            doc.auditado_por = request.user
            doc.processado_em = timezone.now()
            doc.save()
            messages.warning(request, f'Documento "{doc.nome_arquivo}" rejeitado.')
        return redirect('admin_panel:biblioteca')

    return redirect('admin_panel:biblioteca')


@superuser_required
def admin_deletar_documento(request, doc_id):
    """
    Exclui permanentemente um documento e seu arquivo físico.
    """
    from .models import DocumentoBiblioteca
    if request.method == 'POST':
        doc = get_object_or_404(DocumentoBiblioteca, pk=doc_id)
        nome = doc.nome_arquivo
        doc.arquivo.delete()
        doc.delete()
        messages.success(request, f'Documento "{nome}" removido permanentemente.')
    return redirect('admin_panel:biblioteca')


@superuser_required
def admin_deletar_documentos_batch(request):
    """Exclui múltiplos documentos em lote via AJAX."""
    from .models import DocumentoBiblioteca
    if request.method == 'POST':
        ids = request.POST.getlist('doc_ids[]')
        if not ids:
            return JsonResponse({'status': 'error', 'message': 'Nenhum ID recebido.'}, status=400)
        docs = DocumentoBiblioteca.objects.filter(pk__in=ids)
        total = docs.count()
        for doc in docs:
            try:
                doc.arquivo.delete()
            except Exception:
                pass
        docs.delete()
        return JsonResponse({'status': 'ok', 'deleted': total})
    return JsonResponse({'status': 'error'}, status=405)


# ---------------------------------------------------------------------------
# Gestão de Feedback e Curadoria IA (RLHF)
# ---------------------------------------------------------------------------

@superuser_required
def admin_feedback_list(request, tipo):
    """
    Lista usuários que deram feedback (tipo: like ou dislike).
    """
    from chat_ai.models import ChatMessage
    from django.db.models import Count

    if tipo not in ['like', 'dislike']:
        return redirect('admin_panel:dashboard')

    # Agrupa por usuário e conta feedbacks do tipo selecionado
    usuarios_feedback = CustomUser.objects.filter(
        sessions__messages__feedback=tipo
    ).annotate(
        total_feedback=Count('sessions__messages', filter=models.Q(sessions__messages__feedback=tipo))
    ).order_by('-total_feedback')

    context = {
        'usuarios': usuarios_feedback,
        'tipo': tipo,
        'label': 'Curtidas' if tipo == 'like' else 'Não Curtidas'
    }
    return render(request, 'admin_panel/feedback_list.html', context)


@superuser_required
def admin_feedback_messages(request, user_id, tipo):
    """
    Mostra as mensagens específicas de um usuário que receberam feedback.
    """
    from chat_ai.models import ChatMessage, AIConsistencyCorrection
    usuario = get_object_or_404(CustomUser, pk=user_id)
    
    mensagens = ChatMessage.objects.filter(
        session__user=usuario,
        feedback=tipo,
        role='assistant'
    ).select_related('session').order_by('-timestamp')

    context = {
        'usuario': usuario,
        'mensagens': mensagens,
        'tipo': tipo,
        'label': 'Curtidas' if tipo == 'like' else 'Não Curtidas'
    }
    return render(request, 'admin_panel/feedback_messages.html', context)


@superuser_required
def admin_save_correction(request, message_id):
    """
    Grava a sugestão de melhoria do Superusuário para a IA.
    Captura também a pergunta original do usuário para garantir aprendizado perpétuo.
    """
    from chat_ai.models import ChatMessage, AIConsistencyCorrection
    if request.method == 'POST':
        mensagem = get_object_or_404(ChatMessage, pk=message_id)
        titulo   = request.POST.get('titulo_melhoria', '').strip()
        sugestao = request.POST.get('sugestao', '').strip()

        if sugestao:
            # Busca a última mensagem do usuário antes desta resposta da IA
            pergunta_usuario = ChatMessage.objects.filter(
                session=mensagem.session,
                role='user',
                timestamp__lt=mensagem.timestamp
            ).order_by('-timestamp').first()
            
            user_query_text = pergunta_usuario.content if pergunta_usuario else "Pergunta não localizada (histórico incompleto)"

            # Como agora é ForeignKey, buscamos a primeira correção vinculada ou criamos uma nova
            correction = AIConsistencyCorrection.objects.filter(message=mensagem).first()
            if not correction:
                correction = AIConsistencyCorrection(
                    message=mensagem,
                    original_response=mensagem.content,
                    user_query=user_query_text
                )
            
            correction.titulo_melhoria = titulo
            correction.suggested_improvement = sugestao
            correction.curated_by = request.user
            
            # Garante que a query esteja preenchida
            if not correction.user_query or correction.user_query == "Pergunta não localizada (histórico incompleto)":
                correction.user_query = user_query_text
                
            correction.save()
            # Vetoriza a correção no ChromaDB para busca semântica (paráfrases encontram a regra)
            try:
                from chat_ai.llm_engine import AnagmaLLMEngine
                titulo_rlhf = correction.titulo_melhoria or f"RLHF-{correction.id}"
                texto_rlhf = f"Pergunta: {correction.user_query}\nResposta ideal: {correction.suggested_improvement}"
                AnagmaLLMEngine().rag.vetorizar_texto(texto_rlhf, f"RLHF:{titulo_rlhf}")
            except Exception as e:
                print(f"[RAG] Erro ao vetorizar correção RLHF: {e}", flush=True)
            messages.success(request, 'Melhoria técnica gravada com sucesso. Este aprendizado agora é permanente.')

        user_id = mensagem.session.user.id if mensagem.session and mensagem.session.user else None
        if user_id:
            return redirect('admin_panel:feedback_messages', user_id=user_id, tipo=mensagem.feedback)
        return redirect('admin_panel:dashboard')
    
    return redirect('admin_panel:dashboard')


@superuser_required
def admin_deletar_feedback(request, message_id):
    """
    Exclui permanentemente uma mensagem de feedback da IA.
    """
    from chat_ai.models import ChatMessage
    if request.method == 'POST':
        msg = get_object_or_404(ChatMessage, pk=message_id, role='assistant')
        user_id = msg.session.user.id if msg.session and msg.session.user else None
        tipo = msg.feedback
        msg.delete()
        messages.success(request, 'Feedback removido permanentemente.')
        if user_id:
            return redirect('admin_panel:feedback_messages', user_id=user_id, tipo=tipo)
        return redirect('admin_panel:dashboard')
    return redirect('admin_panel:dashboard')


@login_required
def force_password_change(request):
    """
    Página de troca de senha obrigatória. Não permite navegação externa 
    enquanto a senha não for alterada.
    """
    if not request.user.password_change_required:
        return redirect('chat:home')

    if request.method == 'POST':
        nova_senha = request.POST.get('nova_senha', '').strip()
        confirmacao = request.POST.get('confirmacao', '').strip()

        if not nova_senha or nova_senha != confirmacao:
            messages.error(request, 'As senhas não coincidem ou estão vazias.')
        elif len(nova_senha) < 8:
            messages.error(request, 'A senha deve ter pelo menos 8 caracteres.')
        else:
            request.user.set_password(nova_senha)
            request.user.password_change_required = False
            request.user.save()
            # Re-autentica o usuário para não deslogar após trocar a senha
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            messages.success(request, 'Sua senha foi atualizada com sucesso. Bem-vindo(a) à Digiana!')
            return redirect('chat:home')

    return render(request, 'registration/force_password_change.html')

