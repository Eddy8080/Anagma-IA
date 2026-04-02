# Registro de Evolução Técnica - Anagma IA
**Data de Referência:** 02 de Abril de 2026

Este documento serve como memória técnica de longo prazo para a evolução do projeto Banco de Ideias / Anagma IA.

## 1. Identidade Visual e UI/UX (Estética Premium)
- **Favicon Global:** Implementado `Anagma.ico` em todo o sistema (Chat e Painel Admin) com técnica de cache-busting (`?v=1.0`).
- **Avatar Dinâmico da IA:**
    - Logo circular com fundo branco incorporado para harmonia em tema escuro.
    - Animação CSS `ai-breathe` (respiração) para feedback de processamento.
- **Interface Retrátil (Acordeão):** Implementada no Painel de Feedback para organizar curadorias salvas, reduzindo a poluição visual e focando em pendências.
- **Modais Customizados:** Substituição de janelas nativas por modais imersivos centralizados com efeito blur.

## 2. Sistema de Curadoria RLHF e Aprendizado Perpétuo
- **Preservação de Ensino:** Reestruturação do banco de dados para que a exclusão de conversas por usuários comuns **não apague** o aprendizado da IA. O vínculo foi alterado para `SET_NULL` com `ForeignKey`.
- **Auditoria de Autoria:** Implementação do campo `enviado_por` no modelo `DocumentoBiblioteca`. Cada arquivo anexado via chat agora carrega a identidade do autor original para fins de governança e curadoria.
- **Contexto de Pergunta:** Adição do campo `user_query` no modelo de correção, capturando a pergunta original do usuário no momento da curadoria para garantir que o aprendizado mantenha sentido técnico sem o histórico da sessão.
- **Editor Rico (WYSIWYG):** Integrado às ferramentas de correção da IA, permitindo que o superusuário defina a "Resposta Ideal" com formatação premium (Negrito, Itálico, Listas).

## 3. Gestão de Usuários e Governança
- **Exclusão Estratégica:** Modal que permite ao Superusuário escolher entre "Preservar Dados para IA" (anonimização) ou "Purga Total", agora integrado também às listas de feedback.
- **Status de Conta:** Estados Ativo, Inativo e Pausado no modelo `CustomUser`.
- **Segurança de Acesso:** Refinamento do decorador `@superuser_required` para proteção da Biblioteca de Curadoria.

## 4. Arquitetura de Alimentação de Dados (Manual Vivo)
- **Desbloqueio Analítico:** Remoção das travas de governança que impediam a IA de discutir documentos com status "Pendente". O novo mandato supremo ordena que a IA analise o conteúdo extraído imediatamente após o upload.
- **Purificação do RAG:** Otimização da busca semântica para ignorar o título da sessão (ex: "Anexo: ..."), focando exclusivamente no conteúdo técnico do documento para evitar buscas poluídas.
- **Visão Restaurada (String Pura):** Correção do tipo de retorno do processador de texto. A IA agora recebe a string limpa do documento, eliminando a "cegueira" causada pelo tratamento incorreto de tuplas de metadados.

## 5. Engenharia de Modelos e Infraestrutura
- **Fim do Erro de Conexão (Win32):** Tentativa frustrada de otimizar o buffer e fechar handles de arquivo do Django. As mudanças em 02/04 visavam eliminar SegFaults no Windows, mas causaram instabilidade no fluxo de resposta do chat.
- **Modelo Principal:** Phi-3-mini GGUF (Q4_K_M) operando em CPU com consumo de ~2.4 GB de RAM.

## 6. Diário de Crise e Recuperação (02/04/2026)
- **Instabilidade no Chat:** Identificada falha crítica de "Erro de Conexão" ao tentar enviar mensagens ou anexos, resultando em respostas vazias e erros de processamento de JSON no frontend.
- **Tentativa de Restauração Cirúrgica:** Realizada a reversão de arquivos de lógica (`views.py`, etc.), mas o erro persistia devido a uma falha silenciosa na camada de segurança (CSRF).

## 7. Resolução e Estabilização Final (02/04/2026)
- **Causa Raiz Identificada:** O "Erro de Conexão" foi diagnosticado como uma falha de validação CSRF (HTTP 403 Forbidden). A ausência do context processor de CSRF impedia a geração correta do token, e o frontend recebia uma página HTML de erro em vez do JSON esperado.
- **Correção de Backend:** Reintrodução de `django.template.context_processors.csrf` no `settings.py`, garantindo a disponibilidade da variável `{{ csrf_token }}` em todo o ecossistema de templates.
- **Engenharia de Frontend (Robustez):** Implementação de uma nova lógica de captura de token em `home.html`. A função `getCsrf()` agora utiliza uma estratégia de busca em três níveis (Meta Tag -> Cookie -> Input Oculto), eliminando falhas de "token undefined" em sessões persistentes.
- **Estado do Sistema:** **ESTÁVEL.** O fluxo de chat, upload de documentos e processamento pela IA Phi-3-mini foi testado e validado com sucesso. A integridade da comunicação entre o cliente e o servidor está restaurada.

---
*Assinado: Arquiteta e Engenheira de Software Sênior (Sessão 02/04/2026).*
