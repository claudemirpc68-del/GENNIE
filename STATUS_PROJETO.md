# Status e Documentação do Projeto: GENNIE BOT

Data de Atualização: 14/09/2026

---

## 📌 1. Identidade e Propósito
* **Nome do Agente:** GENNIE (Assistente Pessoal Executiva de Elite & Orquestradora com IA).
* **Plataforma:** Telegram (@GENNIE_MAY_BOT | ID: 8912794711).
* **Proprietário:** Claudemir Pedroso Cubas (ID Telegram: 5259328865).
* **Conta de E-mail:** claudemirpc68@gmail.com.
* **Assinatura Oficial:** "Claudemir Pedroso Cubas".
* **Motor LLM:** `openai/gpt-oss-120b` via Groq API (com Function Calling / Tool Calling nativo).
* **Persona:** Mordomo Executivo de Elite (estilo Jarvis / Alta Classe: cortês, refinada, deferente e pontual).

---

## 🟢 2. Estado Atual do Sistema
* **Processo:** ONLINE e em execução com trava de instância única (*Single-Instance Socket Lock*).
* **Validação Automática:** 100% de sucesso em testes automatizados.
* **Autenticação Gmail:** OAuth2 ativo (`token.json` e `client_secret.json` válidos).
* **Segurança Human-in-the-Loop:** Ativa. O bot **nunca** envia ou responde e-mails sem prévia explícita aprovada pelo usuário via Telegram (`sim`, `confirmo` ou `cancelar`).
* **Persistência de Memória:** Ativa em disco via `PicklePersistence` (`gennie_memoria.pickle`).
* **Supervisão da Pasta Downloads:** Ativa via integração direta com `agente_downloads.py` (notificação pontual e automática da rotina diária das 18:00).

---

## 🛠️ 3. Funcionalidades Implementadas

1. **Diálogo Natural e Persona Executiva**:
   - Tratamento cordial e deferente ao Sr. Claudemir Pedroso Cubas.
   - Respostas elegantes a cumprimentos e agradecimentos, com proatividade e pontualidade.
   - Persistência de contexto em disco via `gennie_memoria.pickle`.

2. **Gestão Completa do Gmail**:
   - `listar_emails`: Busca avançada com filtros (`in:inbox`, `is:unread`, `has:attachment`, etc.).
   - `ler_email`: Leitura do conteúdo completo com detecção de anexos.
   - `gerar_briefing`: Síntese executiva diária estruturada com panorama, urgências, avisos e próximos passos.
   - `resumir_thread`: Leitura e síntese de histórico encadeado completo de mensagens.
   - `baixar_anexo`: Download e entrega direta de anexos no Telegram (`reply_document`).
   - `enviar_email` e `responder_email`: Criação com prévia obrigatória (HITL).
   - Organização: `destacar_email`, `lixeira_email`, `marcar_spam`, `aplicar_etiqueta`, `marcar_lido` e `arquivar`.

3. **Supervisão e Notificação da Pasta Downloads**:
   - Conectada ao Agente Local de Downloads (`agente_downloads.py`).
   - Recebe e formata o relatório da faxina diária das 18:00, destacando arquivos classificados, duplicados excluídos e espaço recuperado em disco.

4. **Bridge REST API**:
   - Servidor HTTP assíncrono em `aiohttp` na porta 8000.
   - Autenticação Bearer via `BRIDGE_SECRET_KEY` para consumo por integrações externas.

---

## 📁 4. Arquivos do Projeto
* `gennie.py` — Core do bot Telegram, handlers, ferramentas e persistência.
* `bridge_server.py` — Servidor de API REST HTTP.
* `validar_bot.py` — Diagnóstico e testes automatizados de conexão e regras.
* `autorizar.py` — Fluxo inicial de credenciais OAuth2 do Gmail.
* `STATUS_PROJETO.md` — Documentação do estado do projeto.
* `README.md` — Manual operacional completo do projeto.
