from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import CustomUserRegistrationForm
from .models import GlobalIdeia, CustomUser, PerfilAnagma
from .decorators import superuser_required

class AnagmaLoginView(LoginView):
    """
    View de login customizada para suportar a funcionalidade 'Lembrar-me'.
    """
    template_name = 'registration/login.html'

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

def logout_view(request):
    """
    Garante o encerramento da sessão e redireciona para o login.
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


# Termos que identificam conteúdo do domínio contábil/fiscal/financeiro.
# Verificação por substring com texto normalizado (espaços em volta evitam falsos positivos).
_TERMOS_CONTABEIS = (
    'contab', 'tribut', 'fiscal', ' imposto', 'irpj', 'irpf', 'irrf', 'csll',
    ' pis ', 'cofins', ' iss ', 'icms', ' inss', ' fgts', 'simples nacional',
    'lucro presumido', 'lucro real', ' mei ', 'balanço', 'balancete', ' dre ',
    ' ativo', ' passivo', 'patrimônio', 'receita', 'despesa', 'provisão',
    'depreciação', 'amortizaç', 'fluxo de caixa', ' sped', 'esocial',
    ' ecf ', ' ecd ', ' dctf', 'pgdas', 'nota fiscal', ' nfe', ' nfse',
    'folha de pagamento', 'rescisão', 'auditoria', 'perícia', 'escrituração',
    'lançamento', ' cpc ', ' nbc ', ' cfc ', 'contador', 'tributário',
    'capital social', 'conciliação', 'obrigação acessória', 'regime de caixa',
    'regime de competência', 'demonstração financeira', 'demonstração contábil',
    'custo', 'inventário', 'estoque', 'orçamento', 'financeiro', 'financeira',
    'contabilista', 'escritório contábil', 'decore', 'holerite', 'décimo terceiro',
)


def _eh_ideia_contabil(titulo, conteudo):
    """Retorna True se o texto contém ao menos um termo do domínio contábil."""
    texto = f' {titulo} {conteudo} '.lower()
    return any(termo in texto for termo in _TERMOS_CONTABEIS)


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
            ativa=True,
        )
        messages.success(request, 'Ideia registrada e disponível na base de conhecimento.')
        return redirect('chat:home')

    return render(request, 'core/criar_ideia.html')


# ---------------------------------------------------------------------------
# Painel de superusuários
# ---------------------------------------------------------------------------

@superuser_required
def admin_panel(request):
    from chat_ai.models import ChatSession
    from django.utils import timezone
    hoje = timezone.now().date()
    context = {
        'total_usuarios': CustomUser.objects.count(),
        'total_ideias_ativas': GlobalIdeia.objects.filter(ativa=True).count(),
        'sessoes_hoje': ChatSession.objects.filter(criado_em__date=hoje).count(),
    }
    return render(request, 'admin_panel/dashboard.html', context)


@superuser_required
def admin_usuarios(request):
    usuarios = CustomUser.objects.all().order_by('date_joined')
    return render(request, 'admin_panel/usuarios.html', {'usuarios': usuarios})


@superuser_required
def admin_criar_usuario(request):
    if request.method != 'POST':
        return redirect('admin_panel:usuarios')
    username      = request.POST.get('username', '').strip()
    nome_completo = request.POST.get('nome_completo', '').strip()
    email         = request.POST.get('email', '').strip().lower()
    password      = request.POST.get('password', '').strip()

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
        is_active=dominio_oficial,
    )
    if dominio_oficial:
        messages.success(request, f'Usuário "{u.username}" criado e ativo.')
    else:
        messages.warning(request, f'Usuário "{u.username}" criado como suspenso (e-mail fora de @anagma.com.br). Ative manualmente quando necessário.')
    return redirect('admin_panel:usuarios')


@superuser_required
def admin_deletar_usuario(request, user_id):
    if request.method == 'POST':
        usuario = get_object_or_404(CustomUser, pk=user_id)
        if usuario != request.user:
            usuario.delete()
            messages.success(request, 'Usuário excluído.')
        else:
            messages.error(request, 'Você não pode excluir a própria conta.')
    return redirect('admin_panel:usuarios')


@superuser_required
def admin_toggle_ativo(request, user_id):
    if request.method == 'POST':
        usuario = get_object_or_404(CustomUser, pk=user_id)
        if usuario != request.user:
            usuario.is_active = not usuario.is_active
            usuario.save(update_fields=['is_active'])
    return redirect('admin_panel:usuarios')


@superuser_required
def admin_toggle_superuser(request, user_id):
    if request.method == 'POST':
        usuario = get_object_or_404(CustomUser, pk=user_id)
        if usuario != request.user:
            usuario.is_superuser = not usuario.is_superuser
            usuario.is_staff = usuario.is_superuser
            usuario.save(update_fields=['is_superuser', 'is_staff'])
    return redirect('admin_panel:usuarios')


@superuser_required
def admin_ideias(request):
    ideias = GlobalIdeia.objects.select_related('autor').order_by('-criado_em')
    return render(request, 'admin_panel/ideias.html', {'ideias': ideias})


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
