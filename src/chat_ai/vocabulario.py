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
    'hello', 'hi', 'hey', 'iai beleza?'
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
    # sobre a Anagma IA / Digiana
    'o que é anagma', 'o que e anagma', 'anagma ia',
    'o que é digiana', 'o que e digiana', 'quem é digiana', 'quem e digiana',
    # capacidades gerais
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
    # perguntas sobre as fontes de conhecimento (RAG / 4 pilares)
    'consegue consultar', 'consegue responder consultando',
    'você consulta', 'voce consulta',
    'você acessa', 'voce acessa',
    'acessa a biblioteca', 'consulta a biblioteca',
    # REMOVIDO: 'biblioteca de curadoria' e 'banco de ideias'
    # Esses termos indicam PEDIDO DE BUSCA, não pergunta sobre a IA.
    # Ex: "verifique na biblioteca de curadoria" deve ir ao RAG, não ao interceptor.
    'você lê os documentos', 'voce le os documentos',
    'você usa os documentos', 'voce usa os documentos',
    'acessa os arquivos', 'consulta os arquivos',
    'você aprende', 'voce aprende',
    'seu treinamento', 'seu aprendizado',
    'de onde vem', 'de onde vêm',
    'quais são suas fontes', 'quais sao suas fontes',
    'de onde tira', 'de onde você tira',
    # aprendizado contínuo — como a Digiana evolui
    'novas ideias', 'nova ideia',
    'digiana aprende', 'digiana melhora',
    'aprende e melhora', 'melhora respostas', 'melhora sugestões',
    'fica mais precisa', 'fica melhor',
    'aprendizado contínuo', 'aprendizado continuo',
    'quando são enviados', 'quando é enviado', 'quando enviado',
    'ao enviar', 'ao registrar',
    'enviados arquivos', 'enviadas ideias',
    'arquivo enviado', 'ideia enviada', 'ideia registrada',
    'aprende mais', 'cada vez mais precisa',
    'absorve', 'incorpora',
)

# Pares de palavras que juntas indicam pergunta sobre a IA (independente da ordem)
PARES_SOBRE_IA = (
    ('anagma', 'serve'),
    ('anagma', 'faz'),
    ('anagma', 'funciona'),
    ('anagma', 'usar'),
    ('anagma', 'capaz'),
    ('anagma', 'pode'),
    ('digiana', 'serve'),
    ('digiana', 'faz'),
    ('digiana', 'funciona'),
    ('digiana', 'capaz'),
    ('você', 'serve'),
    ('voce', 'serve'),
    ('vc', 'serve'),
    # Consulta a base de conhecimento
    ('consegue', 'consultar'),
    ('consegue', 'responder'),
    ('consegue', 'acessar'),
    ('você', 'consulta'),
    ('voce', 'consulta'),
    ('vc', 'consulta'),
    ('você', 'acessa'),
    ('voce', 'acessa'),
    ('vc', 'acessa'),
    ('você', 'lê'),
    ('voce', 'le'),
    ('vc', 'le'),
    # Fontes de conhecimento — apenas quando é pergunta SOBRE a IA, não pedido de busca
    ('ideias', 'registradas'),
    ('arquivos', 'enviados'),
    # REMOVIDO: ('arquivos', 'biblioteca'), ('documentos', 'biblioteca'),
    # ('documentos', 'curadoria'), ('ideias', 'banco')
    # Esses pares interceptavam pedidos de busca como "verifique na biblioteca".
    # Aprendizado e evolução
    ('digiana', 'aprende'),
    ('digiana', 'melhora'),
    ('digiana', 'evolui'),
    ('aprende', 'melhora'),
    ('aprende', 'ideia'),
    ('aprende', 'arquivo'),
    ('melhora', 'ideia'),
    ('melhora', 'arquivo'),
    ('enviado', 'ideia'),
    ('enviado', 'arquivo'),
    ('registrada', 'ideia'),
    ('novas', 'ideias'),
    ('nova', 'ideia'),
)

# ---------------------------------------------------------------------------
# Temas fora do domínio contábil/fiscal — interceptados para manter o foco
# ---------------------------------------------------------------------------
GATILHOS_FORA_DO_DOMINIO = (
    # Cultura e Lazer
    'cultura', 'tradição', 'tradicao', 'dança', 'danca', 'música', 'musica',
    'festival', 'festivais', 'festa junina', 'carnaval', 'arte', 'literatura',
    'culinária', 'culinaria', 'gastronomia', 'comida típica', 'receita de',
    # Esportes e Entretenimento
    'esporte', 'futebol', 'copa do mundo', 'olimpíadas', 'olimpiadas',
    'filme', 'série', 'serie', 'cinema', 'famoso', 'celebridade',
    # Turismo e Geral
    'turismo', 'viagem', 'viajar', 'país', 'pais', 'história do brasil', 'geografia',
    'curiosidade', 'me conte sobre', 'dicas de lazer', 'o que fazer em',
    'religião', 'religiao', 'igreja',
)

# Pares que indicam temas fora do domínio
PARES_FORA_DO_DOMINIO = (
    ('brasil', 'cultura'),
    ('brasil', 'tradição'),
    ('brasil', 'tradicao'),
    ('brasil', 'história'),
    ('brasil', 'historia'),
    ('brasil', 'geografia'),
    ('como', 'fazer', 'comida'),
    ('como', 'fazer', 'bolo'),
    # Política PARTIDÁRIA — não bloqueia 'política fiscal' ou 'política tributária'
    ('política', 'partido'),
    ('politica', 'partido'),
    ('política', 'eleição'),
    ('politica', 'eleicao'),
    ('política', 'presidente'),
    ('politica', 'presidente'),
    ('política', 'voto'),
    ('politica', 'voto'),
)

# ---------------------------------------------------------------------------
# Stopwords do RAG — ignoradas na busca semântica para evitar ruído
# ---------------------------------------------------------------------------
STOPWORDS_RAG = frozenset({
    # Saudações e conectivos genéricos
    'bom', 'boa', 'dia', 'tarde', 'noite',
    'ola', 'olá', 'oi', 'tudo', 'bem',
    'você', 'voce', 'para', 'como', 'que',
    'uma', 'uns', 'umas', 'isso', 'esse',
    'essa', 'com', 'sem', 'por', 'nos',
    # Verbos e pronomes curtos que não são siglas contábeis
    'vai', 'vem', 'tem', 'faz', 'dar', 'ver', 'ser',
    'ele', 'ela', 'eles', 'elas', 'seu', 'sua', 'seus',
    'foi', 'era', 'são', 'num', 'nas', 'dos', 'das',
    'aos', 'aí', 'lhe', 'me', 'te', 'se', 'já',
    # Palavras da pergunta que não são termos técnicos
    'fala', 'fale', 'ouviu', 'falar', 'dizer', 'sabe',
    'sobre', 'qual', 'onde', 'quando', 'quem',
    # Verbos de comando/pergunta — descrevem o QUE o usuário quer fazer,
    # não o ASSUNTO que está buscando. Nunca aparecem em documentos contábeis.
    # Ex: "Explique o MEI" → filtrar "explique", buscar apenas "MEI".
    'explique', 'explica', 'explicar', 'explicação', 'explicacao',
    'defina', 'define', 'definir',
    'descreva', 'descreve', 'descrever',
    'detalhe', 'detalhar', 'detalha',
    'comente', 'comenta', 'comentar',
    'mostre', 'mostrar', 'mostra',
    'apresente', 'apresentar', 'apresenta',
    'discorra', 'discorrer',
    'disserte', 'dissertar',
    'resuma', 'resumir', 'resume',
    'liste', 'listar',
    'diga',
    'conte', 'contar',
    # SIGLAS CONTÁBEIS PROTEGIDAS — NUNCA devem estar aqui
    # MEI, CPF, ISS, DAS, IPI, IOF, PIS, DRE, CPC, NBC, CFC,
    # CNPJ, IRPF, IRPJ, IRRF, CSLL, FGTS, INSS, ICMS, SPED,
    # PGDAS, COFINS, ECF, ECD, DCTF — essas NUNCA devem ser stopwords
})

# ---------------------------------------------------------------------------
# Termos de Detecção de Idioma Estrangeiro (Kill-Switch)
# Usados para interceptar respostas que o modelo gera em inglês por erro.
# ---------------------------------------------------------------------------
TERMOS_DETECCAO_INGLES = frozenset({
    ' the ', ' and ', ' with ', ' from ', ' because ', ' certainly ',
    ' however ', ' although ', ' which ', ' where ', ' when ', ' who ',
    ' this ', ' that ', ' these ', ' those ', ' been ', ' have ', ' has ',
    ' will ', ' would ', ' should ', ' could ', ' about ', ' after ',
    ' before ', ' during ', ' through ', ' between ', ' among '
})

# ---------------------------------------------------------------------------
# Termos do domínio contábil/fiscal/financeiro
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
