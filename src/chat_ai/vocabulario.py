"""
Vocabulário Central da Anagma IA
=================================
Ponto único de verdade para todos os conjuntos de termos usados em
interceptação, filtragem semântica e classificação de intenção.

Para adicionar novos gatilhos ou termos, edite apenas este arquivo.
"""

# ---------------------------------------------------------------------------
# Saudações — interceptadas antes de chamar o modelo
# ---------------------------------------------------------------------------
SAUDACOES = frozenset({
    'bom dia', 'boa tarde', 'boa noite',
    'olá', 'ola', 'oi', 'oi!', 'olá!',
    'bom dia!', 'boa tarde!', 'boa noite!',
    'hello', 'hi', 'hey','Iai beleza?'
})

# ---------------------------------------------------------------------------
# Perguntas sobre a própria IA — interceptadas antes de chamar o modelo
# ---------------------------------------------------------------------------
GATILHOS_SOBRE_IA = (
    # variações de "para que serve"
    'para que serve', 'pra que serve',
    'para que você serve', 'pra que você serve',
    'para que voce serve', 'pra que voce serve',
    'você serve', 'voce serve',
    # o que você faz / é
    'o que você faz', 'o que voce faz',
    'o que você é', 'o que voce e',
    'o que é você', 'o que é voce',
    # quem é você
    'quem é você', 'quem é voce', 'quem e voce',
    # sobre a Anagma IA
    'o que é anagma', 'o que e anagma', 'anagma ia',
    # capacidades
    'o que você pode', 'o que voce pode',
    'suas capacidades', 'suas funcionalidades',
    'do que você é capaz', 'do que voce e capaz',
    'quais são suas funções', 'quais sao suas funcoes',
    # como funciona / usar
    'como funciona', 'como você funciona', 'como voce funciona',
    'como usar', 'como te usar', 'como posso usar', 'como posso te usar',
    # pedidos de explicação
    'me explica', 'me explique como',
    'o que você sabe', 'o que voce sabe',
    # ajuda geral
    'pode me ajudar com', 'no que pode ajudar',
    'me ajude a entender',
)

# Pares de palavras que juntas indicam pergunta sobre a IA (independente da ordem)
PARES_SOBRE_IA = (
    ('anagma', 'serve'),
    ('anagma', 'faz'),
    ('anagma', 'funciona'),
    ('anagma', 'usar'),
    ('anagma', 'capaz'),
    ('anagma', 'pode'),
    ('você', 'serve'),
    ('voce', 'serve'),
)

# ---------------------------------------------------------------------------
# Stopwords do RAG — ignoradas na busca semântica para evitar ruído
# ---------------------------------------------------------------------------
STOPWORDS_RAG = frozenset({
    'bom', 'boa', 'dia', 'tarde', 'noite',
    'ola', 'olá', 'oi', 'tudo', 'bem',
    'você', 'voce', 'para', 'como', 'que',
    'uma', 'uns', 'umas', 'isso', 'esse',
    'essa', 'com', 'sem', 'por', 'nos',
})

# ---------------------------------------------------------------------------
# Termos do domínio contábil/fiscal/financeiro
# Usados para validar se uma ideia ou conteúdo pertence ao domínio da Anagma.
# Verificação por substring sobre texto normalizado (lowercase com espaços).
# ---------------------------------------------------------------------------
TERMOS_CONTABEIS = (
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
