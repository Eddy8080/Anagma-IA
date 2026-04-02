from django.shortcuts import render, redirect, get_object_or_404
from django.db import models
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from .forms import CustomUserRegistrationForm
from .models import GlobalIdeia, CustomUser, PerfilAnagma
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
        auth_login(self.request, form.get_user())
        
        if remember_me:
            # Mantém logado por 30 dias
            self.request.session.set_expiry(2592000)
        else:
            # Expira ao fechar o navegador
            self.request.session.set_expiry(0)
            
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
def criar_ideia(request):
    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        conteudo = request.POST.get('conteudo', '').strip()
        if not titulo or not conteudo:
            messages.error(request, 'Preencha título e conteúdo.')
            return render(request, 'core/criar_ideia.html')

        GlobalIdeia.objects.create(
            autor=request.user,
            titulo=titulo,
            conteudo=conteudo,
            ativa=False, # Usuários comuns agora passam por auditoria
        )
        messages.success(request, 'Sua ideia foi enviada para análise técnica e estará disponível em breve.')
        return redirect('chat:home')

    return render(request, 'core/criar_ideia.html')


# ---------------------------------------------------------------------------
# Painel de superusuários
# ---------------------------------------------------------------------------

@superuser_required
def admin_panel(request):
    from chat_ai.models import ChatSession, ChatMessage
    from django.utils import timezone
    hoje = timezone.now().date()
    context = {
        'total_usuarios': CustomUser.objects.count(),
        'total_ideias_ativas': GlobalIdeia.objects.filter(ativa=True).count(),
        'sessoes_hoje': ChatSession.objects.filter(criado_em__date=hoje).count(),
        'total_likes': ChatMessage.objects.filter(feedback='like').count(),
        'total_dislikes': ChatMessage.objects.filter(feedback='dislike').count(),
    }
    return render(request, 'admin_panel/dashboard.html', context)


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
    return render(request, 'admin_panel/biblioteca.html', {'documentos': documentos})


@superuser_required
def admin_upload_biblioteca(request):
    """
    Permite ao Superusuário subir documentos diretamente (já aprovados).
    """
    from .models import DocumentoBiblioteca
    from chat_ai.document_processor import AnagmaDocumentProcessor
    
    if request.method == 'POST' and request.FILES.get('arquivo'):
        uploaded_file = request.FILES['arquivo']
        nome_original = uploaded_file.name
        ext = nome_original.split('.')[-1].lower() if '.' in nome_original else ''
        
        if ext not in ['pdf', 'png', 'jpg', 'jpeg']:
            messages.error(request, 'Extensão de arquivo não suportada.')
            return redirect('admin_panel:biblioteca')

        try:
            # 1. Cria o registro aprovado
            doc = DocumentoBiblioteca.objects.create(
                nome_arquivo=nome_original,
                arquivo=uploaded_file,
                extensao=ext,
                status='approved',
                auditado_por=request.user,
                processado_em=timezone.now()
            )
            
            # 2. Processa o texto imediatamente para a IA aprender
            doc.arquivo.open('rb')
            try:
                texto = AnagmaDocumentProcessor.extrair_texto(doc.arquivo, ext)
            finally:
                doc.arquivo.close()
            doc.conteudo_extraido = texto
            doc.save(update_fields=['conteudo_extraido'])

            if not texto:
                messages.warning(request, f'Documento "{nome_original}" adicionado, mas nenhum texto foi identificado.')
            else:
                messages.success(request, f'Documento "{nome_original}" adicionado e aprovado com sucesso.')
        except Exception as e:
            messages.error(request, f'Erro ao processar documento: {str(e)}')
            
    return redirect('admin_panel:biblioteca')


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
            doc.status = 'approved'
            doc.motivo_rejeicao = ''
            doc.auditado_por = request.user
            doc.processado_em = timezone.now()
            doc.save()
            # Vetoriza no ChromaDB para habilitar busca semântica
            if doc.conteudo_extraido:
                try:
                    from chat_ai.llm_engine import AnagmaLLMEngine
                    AnagmaLLMEngine().rag.vetorizar_texto(doc.conteudo_extraido, doc.nome_arquivo)
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
        doc.arquivo.delete() # Remove o arquivo físico
        doc.delete()
        messages.success(request, f'Documento "{nome}" removido permanentemente.')
    return redirect('admin_panel:biblioteca')


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

