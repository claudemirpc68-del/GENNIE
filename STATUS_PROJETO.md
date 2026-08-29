# Status e Documentação do Projeto: GENNIE BOT

Data de Atualização: 29/08/2026

---

## 📌 1. Identidade e Propósito
* **Nome do Agente:** GENNIE (Assistente pessoal inteligente de e-mails com IA).
* **Plataforma:** Telegram (@GENNIE_MAY_BOT | ID: 8912794711).
* **Proprietário:** Claudemir Pedroso Cubas (ID Telegram: 5259328865).
* **Conta de E-mail:** claudemirpc68@gmail.com.
* **Assinatura Oficial:** "Claudemir Pedroso Cubas".
* **Motor LLM:** `openai/gpt-oss-120b` via Groq API (com Function Calling / Tool Calling nativo).

---

## 🟢 2. Estado Atual do Sistema
* **Processo:** ONLINE e em execução contínua com trava de instância única (*Single-Instance Socket Lock*).
* **Validação Automática:** 100% de sucesso (20/20 testes aprovados em `validar_bot.py`).
* **Autenticação Gmail:** OAuth2 ativo (`token.json` e `client_secret.json` válidos).
* **Segurança Human-in-the-Loop:** Ativa. O bot **nunca** envia ou responde e-mails sem prévia explícita aprovada pelo usuário via Telegram (`sim`, `confirmo` ou `cancelar`).
* **Persistência de Memória:** Ativa em disco via `PicklePersistence` (`gennie_memoria.pickle`).

---

## 🛠️ 3. Funcionalidades Implementadas
1. **Diálogo Natural, Continuidade e Persistência em Disco**:
   - Respostas calorosas e humanas a saudações ("oi", "olá", "bom dia"), agradecimentos ("obrigado", "valeu", "show") e elogios.
   - **Persistência de Memória Ativa (`gennie_memoria.pickle`)**: Histórico de diálogo e rascunhos são salvos em disco.
   - Suporte ao comando `/limpar` (ou em linguagem natural *"limpar memória"*) com confirmação detalhada.
2. **Briefings e Resumos Inteligentes em Lote com IA (Etapa 3 Implementada)**:
   - 📊 **Briefing Executivo Diário (`gerar_briefing` / `/briefing`):** Coleta os e-mails recentes e não lidos em lote, sintetizando urgências, prazos, ações pendentes e notificações em um relatório escaneável.
   - ⚡ **Resumo de Threads (`resumir_thread`):** Analisa conversas encadeadas inteiras, mapeando o histórico cronológico de trocas de mensagens e decisões.
3. **Organização Avançada da Caixa Postal (Etapa 2 Implementada)**:
   - ⭐ **Destaque com Estrela (`destacar_email`):** Adiciona ou remove estrela de e-mails, com indicador visual `⭐ DESTACADO` na listagem.
   - 🏷️ **Etiquetas / Marcadores Customizados (`aplicar_etiqueta`):** Cria novas categorias no Gmail e aplica em mensagens sob demanda.
   - 🗑️ **Lixeira e Exclusão Segura (`lixeira_email`):** Mover mensagens para a lixeira do Gmail ou restaurá-las.
   - 🚫 **Controle de Spam (`marcar_spam`):** Mover e-mails indesejados para a pasta de Spam.
4. **Gestão Completa de Anexos (Etapa 1 Implementada)**:
   - 📥 **Download de Anexos (`baixar_anexo`):** Extrai PDFs, planilhas e imagens do Gmail e entrega diretamente no Telegram.
   - 📤 **Envio de Anexos:** Recebe fotos/documentos do usuário no Telegram e monta e-mails `MIMEMultipart` com prévia de segurança.
   - 🔍 **Filtro de Anexos:** Suporte a consultas com `has:attachment` e `filename:pdf`.
5. **Listagem e Leitura Inteligente**:
   - `listar_emails`: Filtros como `in:inbox`, `is:unread`, `is:starred`, `from:...`.
   - `ler_email`: Decodificação MIME, corpo limpo e listagem de anexos.
6. **Envio e Resposta Seguros (HITL)**:
   - `enviar_email` e `responder_email` com prévia obrigatória e aprovação antes do envio.
7. **Controle de Acesso Exclusivo**:
   - Apenas mensagens do `DONO_ID` são processadas.

---

## 📁 4. Arquivos do Projeto
* `gennie.py`: Código principal do bot Telegram com orquestrador de ferramentas e trava de instância.
* `validar_bot.py`: Bateria com 20 testes automatizados e diagnóstico em tempo real.
* `backup_completo.py` & `backup_gmail.py`: Exportação segura de e-mails em formato JSON.
* `autorizar.py`: Fluxo de autenticação OAuth2 do Google.
* `diagnostico.py`: Inspeção de volumes e pastas do Gmail.
* `.env`: Configurações e tokens sensíveis.
* `gennie_memoria.pickle`: Armazenamento de estado persistente.

---

## 🚀 5. Próximos Passos (Para a próxima sessão)
* Implementar novas ferramentas ou filtros adicionais caso desejado (ex: busca por data, anexos).
* Monitoramento ou logs avançados de execução.
* Integração com outros serviços (Google Calendar / Drive) se planejado.
