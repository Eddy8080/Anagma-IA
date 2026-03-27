# Registro de Evolução Técnica - Anagma IA
**Data de Referência:** 26 de Março de 2026

Este documento serve como memória técnica de longo prazo para a evolução do projeto Banco de Ideias / Anagma IA.

## 1. Identidade Visual e UI/UX (Estética Premium)
- **Favicon Global:** Implementado `Anagma.ico` em todo o sistema (Chat e Painel Admin) com técnica de cache-busting (`?v=1.0`).
- **Avatar Dinâmico da IA:**
    - Logo circular com fundo branco incorporado para harmonia em tema escuro.
    - Animação CSS `ai-breathe` (respiração) para feedback de processamento.
    - Ajuste de escala (`scale 1.1`) para preenchimento total do badge.
- **Modais Customizados:** Substituição de janelas nativas do sistema por modais imersivos centralizados com efeito blur.

## 2. Sistema de Curadoria RLHF (Treinamento IA)
- **Infraestrutura:** Criado modelo `AIConsistencyCorrection` vinculado a feedbacks de mensagens.
- **Fluxo Admin:** 
    - Dashboard interativo com contadores de Likes/Dislikes clicáveis.
    - Agrupamento de feedbacks por usuário para auditoria.
    - Editor de Melhoria: Interface para superusuário gravar a "Resposta Ideal" para a IA.
    - Navegação fluida com botões "Voltar" em todas as telas de feedback.

## 3. Gestão de Usuários e Governança
- **Ordenação:** Lista de usuários agora é carregada em ordem alfabética (Nome Completo > Username).
- **Status de Conta:** Implementados estados Ativo, Inativo e Pausado no modelo `CustomUser`.
- **Exclusão Estratégica:** Modal que permite ao Superusuário escolher entre "Preservar Dados para IA" (anonimização) ou "Purga Total".
- **Nível de Acesso:** Lógica preparada para alternância entre Usuário e Superusuário via Painel Admin.

## 4. Infraestrutura e Estabilidade
- **Settings:** Configuração de `STATICFILES_DIRS` para reconhecimento da pasta global de estáticos.
- **Bugs Corrigidos:** 
    - Resolvidos erros de `TemplateSyntaxError`, `NameError` (importações) e `IndentationError` em arquivos críticos.
    - **Correção dos Seletores (UI):** Restaurada a funcionalidade dos menus suspensos de Perfil e Status no Painel de Usuários.
    - **Correção de Notas de IA:** Implementado filtro no prompt e regex de pós-processamento para remover metadados e notas explicativas do modelo Phi-3.

## 5. Central de Inteligência Documental (Nova Feature)
- **Biblioteca de Curadoria:** Implementada esteira de processamento de documentos (PDF/Imagens) com OCR (PyMuPDF/Tesseract).
- **Limite de Performance:** Extração limitada às primeiras 10 páginas para evitar sobrecarga de RAM/CPU.
- **Fluxo de Auditoria:** Documentos entram em quarentena para aprovação de Superusuários no Painel Admin antes de serem "aprendidos" pela IA.
- **RAG Dinâmico:** IA agora busca conhecimento tanto no ChromaDB (fixo) quanto nos documentos aprovados na Biblioteca (dinâmico).

## 6. Planejamento: Governança e Notificações Oficiais
- **Rastreabilidade de Autoria:** Necessidade de vincular `DocumentoBiblioteca` ao `CustomUser` (autor) para permitir auditoria personalizada.
- **Módulo de Notificações SMTP:** 
    - Implementação de envio de e-mails via conta oficial `anagmaia@anagma.com.br`.
    - Fluxo de Feedback: Disparo automático de e-mail formatado em HTML para o autor quando um documento for rejeitado na auditoria, contendo o "Motivo da Rejeição".
    - Infraestrutura: Uso de variáveis de ambiente (`.env`) para credenciais seguras de SMTP (Host, Port, User, App Password).

## 7. Diretrizes de Implantação e Infraestrutura
- **Domínio Interno (Intranet):** Para permitir o acesso via `http://anagma/` em vez de IPs, deve-se configurar um Registro A no DNS interno apontando o nome "anagma" para o IP do servidor de produção.
- **Mascaramento de Porta (Proxy Reverso):** 
    - Utilizar Nginx ou Apache como servidor de borda na porta 80.
    - Configurar o roteamento interno (proxy_pass) para a porta de execução do Django (ex: 8000).
- **Segurança de Host:** O parâmetro `ALLOWED_HOSTS` no `settings.py` deve ser atualizado para incluir o nome de domínio customizado (`'anagma'`).

## 8. Guia de Evolução do Modelo (Cérebro da IA)
O sistema foi projetado de forma modular, permitindo a substituição do modelo Phi-3 por versões mais recentes (ex: Phi-3.5, Llama-3.2) sem alteração de código fonte.
- **Formato Obrigatório:** O novo modelo deve estar no formato **GGUF** (quantização recomendada: Q4_K_M ou Q5_K_M para equilíbrio entre RAM e precisão).
- **Procedimento de Troca:**
    1. Baixar o novo arquivo `.gguf` (ex: via Hugging Face).
    2. Colocar o arquivo na pasta `assets/models/phi-3-mini-gguf/`.
    3. No arquivo `src/AnagmaCore/settings.py`, atualizar a variável `GGUF_MODEL_PATH` com o novo nome do arquivo.
    4. Reiniciar o servidor para que o Singleton `AnagmaLLMEngine` carregue o novo peso em RAM.
- **Recomendação:** Priorizar modelos compactos (entre 3B e 7B parâmetros) para manter o tempo de resposta aceitável em execuções via CPU.

## 9. Planejamento em Aberto: Arquitetura de Seleção Dinâmica de Modelos
- **Objetivo:** Implementar controle via Painel Admin para alternar entre três estados de performance da IA:
    - **Modo Leve:** Foco em velocidade e baixo consumo de recursos.
    - **Modo Médio:** Equilíbrio atual entre precisão e performance.
    - **Modo Potência Máxima:** Máximo raciocínio lógico e interpretação de contexto para casos complexos.
- **Desafios Técnicos em Pauta:**
    - Gestão de memória RAM durante a troca "a quente" de modelos.
    - Implementação de Singleton recarregável no `AnagmaLLMEngine`.
    - Preservação da integridade do RAG (Memória) independente do motor de processamento escolhido.

- **Git:** Arquivo `google.md` mantido na pasta física para acesso da IA e persistência de memória técnica.

---
*Assinado: Arquiteta e Engenheira de Software Sênior (Sessão 27/03/2026).*

