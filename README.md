# Digiana — Inteligência Contábil da Anagma

A **Digiana** é uma plataforma de Inteligência Artificial local (Edge AI), projetada para ser a autoridade consultiva em Contabilidade Brasileira e Internacional da **Anagma**. Cada resposta é ancorada na biblioteca oficial de documentos e no Banco de Ideias da organização — sem dependência de APIs externas, sem envio de dados para a nuvem.

---

## Arquitetura Geral

```
Usuário → Chat (SSE Streaming)
             ↓
        RAG Híbrido 3 Camadas
             ↓              ↓              ↓
     Semântica       Keyword DB      Via Expressa
     (ChromaDB)    (RLHF / Ideias  (match por nome
                    / Biblioteca)   de arquivo)
             ↓
        Self-Audit (LLM filtra chunks irrelevantes)
             ↓
        Llama 3.1 8B Instruct (GGUF local)
             ↓
        Modo Terminal   /   Modo Transcrição   /   Modo Padrão
        (Excel integral)    (PDF longo integral)   (RAG normal)
```

---

## Stack de Engenharia

| Camada | Tecnologia |
| --- | --- |
| Framework | Python 3.12 / Django 6.0.3 |
| LLM local | Meta Llama 3.1 8B Instruct (GGUF Q4\_K\_M) via `llama-cpp-python` · n\_ctx 16 384 |
| Extração de documentos | **IBM Docling** (PDF, DOCX, XLSX, PPTX — saída Markdown de alta fidelidade) |
| Fallback Excel legado | pandas + xlrd para `.xls` (Excel 97-2003) com detecção automática de cabeçalho |
| Fallback OCR | EasyOCR para imagens (PNG, JPG) |
| Embeddings | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` via HuggingFace |
| Vector Store | ChromaDB persistido em `assets/vector_store/` |
| Streaming | SSE (Server-Sent Events) nativo Django |
| Frontend | HTML5 · CSS3 · marked.js · Quill.js |
| Servidor WSGI | Waitress (Windows) |
| Proxy reverso | Nginx |
| Serviço Windows | NSSM (Non-Sucking Service Manager) |
| Instalador | Inno Setup |
| Banco de dados | SQLite (dev) |

---

## Módulos Principais

### `src/chat_ai`
- **`llm_engine.py`** — Motor de inferência com singleton thread-safe. Gerencia Modo Terminal (Excel), Modo Transcrição (PDFs longos), Self-Audit e guardrails de domínio fechado.
- **`rag_engine.py`** — RAG Híbrido: camada semântica (ChromaDB k=6), camada keyword (RLHF + Ideias + Biblioteca) e Via Expressa por nome de arquivo.
- **`document_processor.py`** — Extração universal via Docling com fallbacks para formatos legados. Suporte a PDF, DOCX, XLSX, XLS, PPTX, TXT, PNG, JPG, DOC.

### `src/core`
- **`models.py`** — `DocumentoBiblioteca` (biblioteca de curadoria com workflow de aprovação), `GlobalIdeia` (banco de ideias), `ChatSession` (sessões com soft-delete e fixação), `PerfilAnagma` (DNA institucional da IA), `ConfiguracaoIA` (status do modelo).
- **`signals.py`** — Vetorização automática ao aprovar documento ou ativar ideia.
- **`management/commands/reextrair_biblioteca.py`** — Re-extrai e re-vetoriza toda a biblioteca aprovada sem re-upload.

---

## Funcionalidades

### Biblioteca de Curadoria
Upload de documentos (PDF, DOCX, XLS, XLSX, PPTX, TXT, imagens) com extração automática via Docling. Workflow de auditoria: Pendente → Aprovado / Rejeitado. Documentos aprovados são vetorizados no ChromaDB via signal.

### Banco de Ideias
Orientações e boas práticas da equipe registradas diretamente no chat. Ativação pelo responsável dispara vetorização automática.

### RLHF via RAG
Correções gravadas pelos responsáveis (`AIConsistencyCorrection`) são vetorizadas e injetadas como contexto em perguntas similares — sem re-treinamento do modelo.

### Self-Audit
O próprio LLM (temperatura 0.0, max\_tokens 80) avalia quais chunks do RAG respondem diretamente à pergunta antes de incluí-los no prompt. Reduz ruído sem hard-code de domínios.

### Modos Especiais de Resposta
- **Modo Terminal** — Ativado quando a busca retorna `ARQUIVO EXCEL INTEGRAL DA CURADORIA`. O LLM transcreve as tabelas markdown integralmente (max\_tokens 4096, preamble stripping).
- **Modo Transcrição** — Ativado quando retorna `DOCUMENTO INTEGRAL DA CURADORIA` (PDFs longos > 4 000 chars). O LLM reproduz o conteúdo de forma fiel sem interpretar.

### Renderização de Tabelas no Chat
Pipeline de pré-processamento aplicado a toda resposta antes do `marked.js`:
1. `stripCodeFences` — remove cercas ` ```markdown ``` ` errôneas do LLM
2. `normalizeSeparators` — corrige separadores GFM inválidos (ex: `|:|` → `| :-- |`)
3. `repairMarkdownTables` — injeta linha separadora quando ausente

---

## Deploy

| Item | Configuração |
| --- | --- |
| Servidor | Windows Server (produção interna) |
| Domínio | `www.anagma.com.br` (acesso interno e externo) |
| WSGI | Waitress servindo Django |
| Proxy | Nginx terminando SSL e servindo estáticos |
| Serviço | NSSM registra Waitress + Nginx como serviços Windows |
| Instalador | Inno Setup empacota tudo para deploy em uma única execução |
| Modelo | `Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf` em `assets/models/` (local, nunca baixado em runtime) |

---

## Status Operacional

**ESTÁVEL E EM PRODUÇÃO**

- Motor ativo: **Digiana 8B** (Llama 3.1 8B Instruct Q4\_K\_M)
- Contexto: 16 384 tokens (budget de entrada: 14 000 tokens)
- Extração: IBM Docling como motor principal; pandas/xlrd como fallback para `.xls`
- Foco atual: qualidade de extração de planilhas Excel e fidelidade de transcrição de PDFs

---

*"A Digiana não apenas lê o conhecimento da Anagma; ela o protege e o torna acionável para toda a equipe em tempo real."*
