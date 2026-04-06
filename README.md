# Digiana - Inteligência Contábil e Gestão de Ideias

A **DigIAna** é uma plataforma avançada de Inteligência Artificial e gestão de conhecimento, desenhada especificamente para o setor contábil. Ela atua como uma especialista em Contabilidade Brasileira e Internacional, integrando o conhecimento técnico especializado à cultura organizacional para potencializar a organização de processos, o refinamento de ideias e a conformidade tributária.

## 🚀 Sobre o Projeto

A Digiana vai além de um simples repositório; ela é um ecossistema cognitivo onde ideias e documentos são processados, categorizados e enriquecidos. Com um mandato de autoridade técnica, a IA utiliza um tom assertivo e proativo ("A análise técnica indica...", "O procedimento correto é...") para guiar colaboradores na estruturação de processos fiscais e consultivos, sempre respeitando os valores da organização.

### Principais Funcionalidades

- **Identidade Digiana:** IA configurada com Perfil Singleton, garantindo posicionamento como autoridade no domínio contábil e fiscal.
- **Arquitetura Hot-Swap (Cérebro Chaveável):** Gestão dinâmica de modelos entre **Digiana-LEVE** (GGUF ~2.4GB) e **Digiana-COMPLETO** (Safetensors ~5GB), com fallback automático e hibernação inteligente.
- **Segurança de Domínio (Guardrails):** Interceptores que garantem o foco estrito em temas contábeis e bloqueio global de idiomas (Language Lock em PT-BR).
- **RAG (Retrieval-Augmented Generation):** Exploração inteligente de contextos baseada em biblioteca de documentos internos e normas contábeis vigentes.
- **Validações Corporativas (Zoho Mail):** Integração com API Zoho via OAuth 2.0 para validação de identidade e governança de acesso (@anagma.com.br).
- **Painel Administrativo Robusto:** Controle de usuários, feedback de mensagens, gestão de modelos de IA e visibilidade global de ideias.

## 🛠️ Tecnologias Principais

- **Backend:** Python / Django 5.x
- **IA/ML:** Motores de Inferência Local (llama.cpp / GGUF), Vector Stores (FAISS/ChromaDB) e LangChain.
- **Infraestrutura:** AlmaLinux 9 (VPS NVMe), Nginx, Gunicorn e Systemd.
- **Frontend:** HTML5, CSS3, JavaScript (Vanilla) com temas dinâmicos (Light/Dark).

## 📂 Estrutura do Projeto

O projeto é organizado para separar a lógica de negócio da inteligência artificial:

- `/src/core`: Gestão de usuários, perfis, ideias globais e integração Zoho.
- `/src/chat_ai`: Motores de IA (LLM Engine), lógica de RAG, Guardrails e processamento de documentos.
- `/assets`: Armazenamento de vetores, modelos de IA e biblioteca de documentos.

## 🚧 Status do Desenvolvimento

O sistema está **ESTÁVEL E PRONTO PARA ESCALAR**. Atualmente operando com o modelo Phi-3-mini GGUF e Guardrails ativos. O foco atual reside na expansão da base de conhecimento (RAG) e no refinamento da curadoria de aprendizado organizacional através do Painel Admin.

---

**Nota:** A Digiana prioriza a execução **local** de inteligência (Edge AI) para garantir a privacidade absoluta e a soberania dos dados estratégicos e contábeis da organização.
