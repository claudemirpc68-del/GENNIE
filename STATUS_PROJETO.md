# Status e Documentação do Projeto: GENNIE BOT

Data de Atualização: 15/08/2026

---

## 📌 1. Identidade e Propósito
* **Nome do Agente:** GENNIE (Assistente pessoal inteligente de e-mails com IA).
* **Plataforma:** Telegram (@GENNIE_MAY_BOT | ID: 8912794711).
* **Proprietário:** Claudemir Pedroso Cubas (ID Telegram: 5259328865).
* **Conta de E-mail:** claudemirpc68@gmail.com.
* **Assinatura Oficial:** "Claudemir Pedroso Cubas".
* **Motor LLM:** `llama-3.3-70b-versatile` via Groq API (com Function Calling / Tool Calling).

---

## 🟢 2. Estado Atual do Sistema
* **Processo:** ONLINE e em execução contínua no sistema operacional (PID `14156`).
* **Validação Automática:** 100% de sucesso (15/15 testes aprovados em `validar_bot.py`).
* **Autenticação Gmail:** OAuth2 ativo (`token.json` e `client_secret.json` válidos).
* **Segurança Human-in-the-Loop:** Ativa. O bot **nunca** envia ou responde e-mails sem prévia explícita aprovada pelo usuário via Telegram (`sim`, `confirmo` ou `cancelar`).

---

## 🛠️ 3. Funcionalidades Implementadas
1. **Diálogo Natural e Continuidade de Conversa**:
   - Respostas calorosas e humanas a saudações ("oi", "olá", "bom dia"), agradecimentos ("obrigado", "valeu", "show") e elogios.
   - Preservação do histórico de contexto após confirmação ou cancelamento de ações.
2. **Listagem de E-mails (`listar_emails`)**:
   - Suporte a filtros Gmail (`in:inbox`, `in:inbox is:unread`, `from:...`, `subject:...`).
   - Destaque para e-mails não lidos (`🔴 NÃO LIDO`).
3. **Leitura de E-mails (`ler_email`)**:
   - Decodificação MIME de texto e limpeza do corpo da mensagem pelo ID.
4. **Envio de Novos E-mails (`enviar_email`)**:
   - Criação de rascunho com prévia, exigindo confirmação explícita antes do envio.
5. **Resposta Encadeada (`responder_email`)**:
   - Preserva `In-Reply-To`, `References` e prefixo `Re:`, exigindo confirmação antes do envio.
6. **Organização da Caixa Postal**:
   - `marcar_lido`: Remove etiqueta `UNREAD`.
   - `arquivar`: Remove etiqueta `INBOX`.
7. **Controle de Acesso**:
   - Apenas mensagens do `DONO_ID` são processadas.

---

## 📁 4. Arquivos do Projeto
* `gennie.py`: Código principal do bot Telegram e orquestrador de ferramentas.
* `validar_bot.py`: Bateria completa de testes automatizados e diagnóstico de ponta a ponta.
* `backup_completo.py` & `backup_gmail.py`: Exportação segura de e-mails em formato JSON.
* `autorizar.py`: Fluxo de autenticação OAuth2 do Google.
* `diagnostico.py`: Inspeção de volumes e pastas do Gmail.
* `.env`: Configurações e tokens sensíveis.

---

## 🚀 5. Próximos Passos (Para a próxima sessão)
* Implementar novas ferramentas ou filtros adicionais caso desejado (ex: busca por data, anexos).
* Monitoramento ou logs avançados de execução.
* Integração com outros serviços (Google Calendar / Drive) se planejado.
