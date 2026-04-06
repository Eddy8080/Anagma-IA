# Registro de Evolução Técnica - Anagma IA (Digiana)
**Data de Referência:** 06 de Abril de 2026

Este documento serve como memória técnica de longo prazo para a evolução do projeto Banco de Ideias / Digiana IA.

## 1. Identidade e Autoridade Técnica (A Digiana)
- **Transição de Marca:** A IA agora é oficialmente identificada como **Digiana**, a especialista em Contabilidade Brasileira e Internacional.
- **Mandato de Autoridade:** Removida a linguagem passiva ("eu recomendaria"). A Digiana agora utiliza tons assertivos e proativos ("A análise técnica indica...", "O procedimento correto é...").
- **DNA Contábil:** Configuração de Perfil Singleton no Banco de Dados que garante que a IA sempre se posicione como autoridade no domínio fiscal e tributário.

## 2. Segurança de Domínio e Linguística (Guardrails)
- **Restrição de Domínio:** Implementação de interceptores (Guardrails) que bloqueiam perguntas sobre temas irrelevantes (cultura, lazer, esportes). A IA recusa educadamente e convida o usuário a retornar ao foco contábil.
- **Bloqueio Global de Idioma (Language Lock):** Implementação de mandato supremo no prompt para impedir respostas em inglês.
- **Kill-Switch de Idioma (Saída):** Filtro de segurança que analisa a resposta gerada e bloqueia a entrega caso o modelo base falhe e produza texto em inglês, garantindo 100% de conformidade com o Português Brasileiro (PT-BR).

## 3. Arquitetura de Cérebro Chaveável (Hot-Swap)
- **Menu de Modelos no Admin:** Novo menu "Modelos de IA" permitindo a escolha entre **Digiana-LEVE** (GGUF ~2.4GB) e **Digiana-COMPLETO** (Safetensors ~5GB).
- **Gestão de Memória Dinâmica:** Implementação de lógicas de "Hot-Swap" com limpeza agressiva de RAM (`gc.collect`) e troca de modelos em tempo real sem interrupção do serviço.
- **Hibernação Inteligente (Fallback):** Sistema de segurança que recua automaticamente para o modelo Leve caso o modelo Completo falhe por falta de recursos ou arquivos ausentes.
- **Feedback Visual de Ativação:** Barra de progresso dinâmica no Painel Admin com reporte de etapas narrativas reais (Limpando memória, Sincronizando aprendizado, Preparando modelo).

## 4. Infraestrutura e Deploy (Cloud Readiness)
- **Estudo de Viabilidade VPS NVMe 8:** Validação técnica para uso de 8GB RAM DDR5 e 4 vCPUs no AlmaLinux 9.
- **Kit de Deploy Automatizado:** Criação dos arquivos `setup_vps_almalinux.sh`, `digiana.service` (Systemd) e `digiana_nginx.conf`.
- **Estratégia Headless:** O servidor opera via terminal (PuTTY), eliminando a necessidade de VSCode ou interfaces gráficas em produção.

## 5. Camada de Segurança e Validação de Identidade (Zoho Mail)
- **Validação via API:** Implementação do `ZohoSecurityManager` para validar e-mails `@anagma.com.br` diretamente no servidor oficial do Zoho Mail via OAuth 2.0.
- **Governança de Acesso:** Bloqueio automático de acesso à IA caso o usuário seja desativado na organização.

## 6. Estudo Técnico de Build e Deploy (Linux vs. Windows)
- **Filosofia de Artefatos:** No AlmaLinux, substituímos o conceito de "Instalador" (.iss/.exe) pelo conceito de "Artefato de Produção" (.tar.gz).
- **Build de Produção (`build_linux.sh`):** Proposta de script que limpa o código (remove cache, venv de windows e git) e gera um pacote compacto pronto para a VPS.
- **Deploy via Terminal:** Uso de ferramentas como `PSCP` (PuTTY) para envio de build do Windows para Linux e `Systemd` como o instalador profissional que gerencia a Digiana como um serviço nativo do sistema.

## 7. Estado Atual do Sistema
- **Status:** **ESTÁVEL E PRONTO PARA ESCALAR.**
- **Motor Principal:** Phi-3-mini GGUF com Guardrails e Identidade Digiana ativos.
- **Perfil Digiana:** Interface de curadoria atualizada para permitir a inserção da história e foco da empresa de forma estruturada.

---
*Assinado: Analista e Desenvolvedor de Sistemas Edilson Monteiro Neto (Sessão 06/04/2026).*
