# 🤖 GENNIE BOT — Assistente Inteligente de E-mails via Telegram

O **GENNIE** é um assistente pessoal inteligente de gerenciamento de e-mails integrado ao **Telegram** e ao **Gmail**, potencializado por Modelos de Linguagem Avançados (LLM via Groq / Llama 3.3 70B) com suporte nativo a **Function Calling (Tool Calling)** e segurança **Human-in-the-Loop**.

---

## ✨ Principais Funcionalidades

* 📬 **Listagem Inteligente (`listar_emails`)**: Busca e-mails na caixa de entrada, destaca mensagens não lidas e suporta filtros de pesquisa do Gmail.
* 📖 **Leitura Direta (`ler_email`)**: Decodifica e apresenta o corpo dos e-mails pelo ID.
* 🔒 **Segurança no Envio com Confirmação (`enviar_email`)**: Prepara o e-mail e apresenta uma prévia para o usuário no Telegram, exigindo aprovação explícita (`sim` / `cancelar`) antes de disparar.
* ✉️ **Respostas Encadeadas (`responder_email`)**: Responde threads mantendo `In-Reply-To`, referências e histórico, com trava de confirmação.
* 🗄️ **Organização da Caixa Postal**: Marca e-mails como lidos (`marcar_lido`) ou arquiva mensagens (`arquivar`).
* 💬 **Diálogo Natural e Empático**: Respostas humanas e fluidas a saudações, agradecimentos e conversação contínua.
* 🛡️ **Assinatura Oficial Automática**: Gestão inteligente de rodapé para evitar duplicações.

---

## 🛠️ Tecnologias Utilizadas

* **Linguagem:** Python 3.10+
* **Framework Telegram:** `python-telegram-bot` (v20+)
* **Google APIs:** `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`
* **LLM Engine:** Groq API (`llama-3.3-70b-versatile` / `deepseek`)
* **Requisições:** `httpx`

---

## 🚀 Como Configurar e Executar

### 1. Clonar o repositório
```bash
git clone https://github.com/claudemirpc68-del/GENNIE.git
cd GENNIE
```

### 2. Instalar dependências
```bash
pip install -r requirements.txt
```

### 3. Configurar Variáveis de Ambiente
Crie um arquivo `.env` baseado no `.env.example`:
```env
TELEGRAM_TOKEN=seu_telegram_bot_token
DONO_ID=seu_telegram_user_id
DEEPSEEK_API_KEY=sua_groq_ou_deepseek_api_key
DEEPSEEK_MODEL=llama-3.3-70b-versatile
DEEPSEEK_URL=https://api.groq.com/openai/v1/chat/completions
```

### 4. Configurar Autenticação do Google
1. Baixe suas credenciais do Google Cloud Console (`OAuth 2.0 Client IDs`) e salve como `client_secret.json` na raiz do projeto.
2. Execute o fluxo inicial de autorização:
```bash
python autorizar.py
```

### 5. Executar o Bot
```bash
python gennie.py
```

---

## 🧪 Validação e Testes Automatizados

Para testar todas as conexões (Telegram, Gmail API, LLM, Tools e Trava de Segurança), execute:
```bash
python validar_bot.py
```

---

## 📄 Licença
Distribuído sob a licença MIT.
