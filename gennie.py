import base64
import json
import logging
import re
import sys
from email.mime.text import MIMEText
from pathlib import Path

# Garante suporte a UTF-8 no terminal Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import httpx
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

BASE = Path(__file__).resolve().parent
ENV_FILE = BASE / ".env"
CLIENT_SECRET = BASE / "client_secret.json"
TOKEN_FILE = BASE / "token.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]
ASSINATURA = "Claudemir Pedroso Cubas"
CONTA = "claudemirpc68@gmail.com"

TOKEN = None
DONO_ID = "5259328865"
API_KEY = None
MODEL = "llama-3.3-70b-versatile"
API_URL = "https://api.groq.com/openai/v1/chat/completions"


def carregar_env():
    global TOKEN, DONO_ID, API_KEY, MODEL, API_URL
    if ENV_FILE.exists():
        for linha in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if linha.startswith("TELEGRAM_TOKEN="):
                val = linha.split("=", 1)[1].strip()
                if val:
                    TOKEN = val
            elif linha.startswith("DONO_ID="):
                val = linha.split("=", 1)[1].strip()
                if val:
                    DONO_ID = val
            elif linha.startswith("DEEPSEEK_API_KEY="):
                val = linha.split("=", 1)[1].strip()
                if val:
                    API_KEY = val
            elif linha.startswith("DEEPSEEK_MODEL="):
                val = linha.split("=", 1)[1].strip()
                if val:
                    MODEL = val
            elif linha.startswith("DEEPSEEK_URL="):
                val = linha.split("=", 1)[1].strip()
                if val:
                    API_URL = val


def autorizado(update: Update):
    if not update.effective_chat:
        return False
    chat_id = str(update.effective_chat.id)
    if chat_id == str(DONO_ID):
        return True
    logging.warning("Tentativa de acesso não autorizado do chat_id: %s (Dono configurado: %s)", chat_id, DONO_ID)
    return False


def get_gmail_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return build("gmail", "v1", credentials=creds)


def listar_emails(service, query="in:inbox", max_results=5):
    resultado = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    msgs = resultado.get("messages", [])
    emails = []
    for m in msgs:
        det = service.users().messages().get(
            userId="me", id=m["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()
        headers = {h["name"].lower(): h["value"] for h in det.get("payload", {}).get("headers", [])}
        nao_lido = "UNREAD" in det.get("labelIds", [])
        emails.append({
            "id": det["id"],
            "from": headers.get("from", "?"),
            "subject": headers.get("subject", "(sem assunto)"),
            "date": headers.get("date", ""),
            "unread": nao_lido,
        })
    return emails


def ler_email(service, msg_id):
    det = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    payload = det.get("payload", {})
    headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
    corpo = ""
    if payload.get("body", {}).get("data"):
        corpo = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    else:
        for p in payload.get("parts", []):
            if p.get("mimeType") == "text/plain" and p.get("body", {}).get("data"):
                corpo = base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", errors="replace")
                break
    return {
        "id": det["id"],
        "from": headers.get("from", "?"),
        "subject": headers.get("subject", "(sem assunto)"),
        "date": headers.get("date", ""),
        "body": corpo.strip()[:5000],
    }


def marcar_lido(service, msg_id):
    service.users().messages().modify(
        userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}
    ).execute()


def arquivar(service, msg_id):
    service.users().messages().modify(
        userId="me", id=msg_id, body={"removeLabelIds": ["INBOX"]}
    ).execute()


def formatar_corpo_com_assinatura(corpo: str) -> str:
    texto = (corpo or "").strip()
    if ASSINATURA.lower() in texto.lower()[-len(ASSINATURA)-40:]:
        return texto
    return f"{texto}\n\n{ASSINATURA}"


def enviar_email(service, dest, assunto, corpo):
    corpo_completo = formatar_corpo_com_assinatura(corpo)
    m = MIMEText(corpo_completo, "plain", "utf-8")
    m["To"] = dest
    m["From"] = CONTA
    m["Subject"] = assunto
    raw = base64.urlsafe_b64encode(m.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


def responder_email(service, msg_id, corpo):
    det = service.users().messages().get(
        userId="me", id=msg_id, format="metadata",
        metadataHeaders=["From", "Subject", "References", "Message-ID"],
    ).execute()
    headers = {h["name"].lower(): h["value"] for h in det.get("payload", {}).get("headers", [])}
    dest = headers.get("from", "")
    if "<" in dest:
        dest = dest.split("<")[1].split(">")[0]
    refs = (headers.get("references", "") or "").strip()
    msgid = headers.get("message-id", "") or ""
    refs = f"{refs} {msgid}".strip()
    assunto = headers.get("subject", "")
    if not assunto.lower().startswith("re:"):
        assunto = f"Re: {assunto}"
    corpo_completo = formatar_corpo_com_assinatura(corpo)
    m = MIMEText(corpo_completo, "plain", "utf-8")
    m["To"] = dest
    m["From"] = CONTA
    m["Subject"] = assunto
    m["In-Reply-To"] = msgid
    m["References"] = refs
    raw = base64.urlsafe_b64encode(m.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return dest, assunto


SYSTEM_PROMPT = f"""Você é o GENNIE, um assistente pessoal inteligente de e-mails que atende pelo Telegram.

IDENTIDADE & PERSONALIDADE
- Nome: GENNIE (inspirado no gênio dos filmes — seja simpático, ágil, prestativo, bem-humorado e caloroso).
- Você gerencia a conta de e-mail: {CONTA}
- Assinatura oficial: {ASSINATURA} (o sistema anexa a assinatura automaticamente no final de cada envio; logo, você NÃO precisa repetir o nome completo dentro do argumento 'corpo').

COMUNICAÇÃO & CONTINUIDADE DE DIÁLOGO
- Responda sempre em português do Brasil (pt-BR) de forma humana, fluida, educada e carismática.
- Sempre responda com uma saudação simpática e receptiva quando o usuário disser "oi", "olá", "bom dia", "boa tarde", etc.
- Ao receber agradecimentos ("obrigado", "valeu", "show", "muito bom", "perfeito", "excelente", "ótimo"), responda com simpatia e naturalidade (ex: "Por nada! Fico muito feliz em ajudar!", "Disponha sempre! Se precisar de mais alguma coisa nos e-mails, é só chamar! 😊").
- Mantenha a continuidade da conversa: quando uma tarefa ou e-mail for concluído, coloque-se à disposição para os próximos passos ou novos comandos de forma leve, sem soar repetitivo ou mecânico.
- Se o usuário conversar, fizer comentários casuais ou elogios, interaja com naturalidade mantendo o tom de um assistente pessoal de confiança.

REGRAS OBRIGATÓRIAS
1. NUNCA envie ou responda qualquer e-mail sem antes apresentar uma prévia ao usuário e obter autorização explícita.
2. Para enviar/responder, use as ferramentas enviar_email/responder_email, que criam a prévia e aguardam a confirmação. A própria ferramenta cuida disso — apenas relate ao usuário o que foi preparado de forma clara e amigável.
3. Ao listar e-mails, destaque os não lidos e categorize por prioridade quando fizer sentido (urgente, importante, informativo).
4. Não invente e-mails, IDs ou informações. Use as ferramentas para consultar dados reais.
5. Se o usuário pedir algo fora das suas capacidades, explique com educação e bom humor.

CAPACIDADES
- listar_emails: busca e-mails (caixa de entrada, não lidos, por remetente/assunto).
- ler_email: lê o conteúdo completo de um e-mail pelo ID.
- enviar_email: cria um e-mail novo (exige aprovação antes do envio).
- responder_email: responde a um e-mail existente (exige aprovação antes do envio).
- marcar_lido / arquivar: organizam a caixa de entrada.

EXEMPLOS DE INTERAÇÃO
- "oi" / "olá" → "Olá! Tudo bem? Como posso te ajudar com seus e-mails hoje?"
- "veja meus emails" / "tem email novo?" → listar_emails
- "leia o email 19bae30da4cb2ea5" → ler_email
- "responda o email sobre a reunião" → identifique o e-mail e use responder_email
- "envie um email para joao@x.com..." → enviar_email
- "obrigado!" / "valeu GENNIE" → "Por nada! Fico sempre às ordens. Se precisar de mais algo, só me avisar! 😊"
- "arquive os emails do banco" → arquivar"""


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "listar_emails",
            "description": "Lista e-mails da conta (por padrão a caixa de entrada). Use para 'veja meus emails', 'tem email novo?', 'emails não lidos'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Filtro Gmail, ex: 'in:inbox', 'in:inbox is:unread', 'from:alguem@x.com', 'subject:algo'."},
                    "max_results": {"type": "integer", "description": "Quantidade máxima (padrão 5)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ler_email",
            "description": "Lê o conteúdo completo de um e-mail pelo ID. Use o ID exibido na listagem.",
            "parameters": {
                "type": "object",
                "properties": {
                    "msg_id": {"type": "string", "description": "ID do e-mail."},
                },
                "required": ["msg_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "enviar_email",
            "description": "Prepara o envio de um e-mail novo. NUNCA envia sem a prévia ser confirmada pelo usuário — a ferramenta cuida da aprovação.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dest": {"type": "string", "description": "E-mail do destinatário."},
                    "assunto": {"type": "string"},
                    "corpo": {"type": "string"},
                },
                "required": ["dest", "assunto", "corpo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "responder_email",
            "description": "Prepara uma resposta para um e-mail existente. NUNCA envia sem a prévia ser confirmada pelo usuário — a ferramenta cuida da aprovação.",
            "parameters": {
                "type": "object",
                "properties": {
                    "msg_id": {"type": "string", "description": "ID do e-mail a responder."},
                    "corpo": {"type": "string"},
                },
                "required": ["msg_id", "corpo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "marcar_lido",
            "description": "Marca um e-mail como lido.",
            "parameters": {
                "type": "object",
                "properties": {
                    "msg_id": {"type": "string"},
                },
                "required": ["msg_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "arquivar",
            "description": "Arquiva um e-mail (remove da caixa de entrada).",
            "parameters": {
                "type": "object",
                "properties": {
                    "msg_id": {"type": "string"},
                },
                "required": ["msg_id"],
            },
        },
    },
]


def chamar_deepseek(messages, tools=None, tool_choice="auto"):
    body = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.2,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = tool_choice
    r = httpx.post(
        API_URL,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json=body,
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def executar_tool(service, user_data, name, arguments):
    if name == "listar_emails":
        emails = listar_emails(
            service,
            query=arguments.get("query", "in:inbox"),
            max_results=int(arguments.get("max_results", 5)),
        )
        if not emails:
            return json.dumps({"resultado": "Nenhum e-mail encontrado."}, ensure_ascii=False)
        linhas = []
        for e in emails:
            marca = "🔴 NAO LIDO" if e["unread"] else "lido"
            linhas.append(f"ID: {e['id']} | {marca}\nDe: {e['from']}\nAssunto: {e['subject']}\nData: {e['date']}")
        return json.dumps({"emails": linhas}, ensure_ascii=False)

    if name == "ler_email":
        email = ler_email(service, arguments["msg_id"])
        return json.dumps(email, ensure_ascii=False)

    if name == "enviar_email":
        corpo_final = formatar_corpo_com_assinatura(arguments.get("corpo", ""))
        user_data["draft"] = {
            "acao": "enviar",
            "dest": arguments["dest"],
            "assunto": arguments.get("assunto", ""),
            "corpo": corpo_final,
        }
        return json.dumps({
            "acao": "PEDIR_APROVACAO",
            "msg": (
                f"Prévia do e-mail:\nPara: {arguments['dest']}\nAssunto: {arguments.get('assunto','')}\n\n"
                f"Mensagem:\n{corpo_final}\n\nResponda 'sim' para enviar ou 'cancelar'."
            ),
        }, ensure_ascii=False)

    if name == "responder_email":
        corpo_final = formatar_corpo_com_assinatura(arguments.get("corpo", ""))
        user_data["draft"] = {
            "acao": "responder",
            "msg_id": arguments["msg_id"],
            "corpo": corpo_final,
        }
        return json.dumps({
            "acao": "PEDIR_APROVACAO",
            "msg": (
                f"Prévia da resposta ao e-mail {arguments['msg_id']}:\n\n{corpo_final}\n\n"
                f"Responda 'sim' para enviar ou 'cancelar'."
            ),
        }, ensure_ascii=False)

    if name == "marcar_lido":
        marcar_lido(service, arguments["msg_id"])
        return json.dumps({"resultado": f"E-mail {arguments['msg_id']} marcado como lido."}, ensure_ascii=False)

    if name == "arquivar":
        arquivar(service, arguments["msg_id"])
        return json.dumps({"resultado": f"E-mail {arguments['msg_id']} arquivado."}, ensure_ascii=False)

    return json.dumps({"erro": "Ferramenta desconhecida."}, ensure_ascii=False)


def confirmar_e_envio(service, draft):
    if draft["acao"] == "enviar":
        enviar_email(service, draft["dest"], draft["assunto"], draft["corpo"])
        return f"✅ Pronto! E-mail enviado com sucesso para {draft['dest']} | Assunto: '{draft['assunto']}'.\n\nSe precisar de mais alguma coisa, é só falar! 😊"
    if draft["acao"] == "responder":
        dest, assunto = responder_email(service, draft["msg_id"], draft["corpo"])
        return f"✅ Resposta enviada com sucesso para {dest} | Assunto: '{assunto}'!\n\nPosso te ajudar com mais algum e-mail?"
    return "Nada pendente para envio."


async def comando_start(update: Update, context):
    if not autorizado(update):
        return
    logging.info("Comando /start recebido de %s", update.effective_chat.id)
    await update.message.reply_text(
        "Olá! Sou o GENNIE, seu assistente de e-mail com IA. 😊\n\n"
        "Pode pedir com palavras simples, por exemplo:\n"
        "📬 \"veja meus emails\"\n"
        "📥 \"tem email novo?\"\n"
        "📖 \"leia o email <id>\"\n"
        "✉️ \"responda o email sobre...\"\n"
        "🆕 \"envie um email para <email>: assunto e mensagem\"\n"
        "🗄️ \"arquive os emails do banco\""
    )


async def processar_mensagem(update: Update, context):
    if not autorizado(update):
        return
    texto = update.message.text.strip()
    logging.info("Mensagem recebida de %s: '%s'", update.effective_chat.id, texto)
    t = texto.lower()

    if not API_KEY:
        await update.message.reply_text("DeepSeek API não configurada.")
        return

    service = get_gmail_service()

    draft = context.user_data.get("draft")
    if draft:
        if t in ("sim", "confirmo", "pode enviar", "pode mandar", "sim, envie", "sim, pode enviar", "ok", "manda", "envia"):
            try:
                resultado = confirmar_e_envio(service, draft)
            except Exception as e:
                resultado = f"Ops, ocorreu um erro ao enviar o e-mail: {e}"
            context.user_data.pop("draft", None)
            
            # Mantém histórico para continuidade da conversa
            hist = context.user_data.get("hist", [])
            hist.append({"role": "user", "content": texto})
            hist.append({"role": "assistant", "content": resultado})
            context.user_data["hist"] = hist[-20:]
            
            await update.message.reply_text(resultado)
            return

        if "cancelar" in t or "não" in t or "cancela" in t:
            context.user_data.pop("draft", None)
            msg_cancel = "Sem problemas! O envio foi cancelado. Se precisar de mais alguma coisa, estou por aqui! 😊"
            hist = context.user_data.get("hist", [])
            hist.append({"role": "user", "content": texto})
            hist.append({"role": "assistant", "content": msg_cancel})
            context.user_data["hist"] = hist[-20:]
            
            await update.message.reply_text(msg_cancel)
            return

    try:
        resposta = await agente_llm(service, context.user_data, texto)
    except Exception as e:
        logging.exception("Erro no agente")
        resposta = f"Ops! Ocorreu um erro: {e}"
    await update.message.reply_text(resposta[:4000])


async def agente_llm(service, user_data, texto):
    hist = user_data.get("hist", [])
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + hist + [
        {"role": "user", "content": texto}
    ]

    for _ in range(6):
        resp = chamar_deepseek(messages, tools=TOOLS)
        msg = resp["choices"][0]["message"]

        if msg.get("tool_calls"):
            messages.append(msg)
            for tc in msg["tool_calls"]:
                fn = tc["function"]
                try:
                    arguments = json.loads(fn["arguments"] or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                resultado = executar_tool(service, user_data, fn["name"], arguments)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": resultado,
                })
            continue

        final = msg.get("content", "").strip()
        hist = (user_data.get("hist", []) + [
            {"role": "user", "content": texto},
            {"role": "assistant", "content": final},
        ])[-20:]
        user_data["hist"] = hist
        return final

    return "Não consegui processar a solicitação. Tente novamente."


async def erro_global(update: Update, context):
    logging.exception("Erro não tratado: %s", context.error)
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Ops! Ocorreu um erro ao processar. Tente novamente em alguns segundos."
            )
        except Exception:
            pass


def main():
    logging.basicConfig(level=logging.INFO)
    carregar_env()
    if not TOKEN:
        print("TELEGRAM_TOKEN não configurado. Adicione ao .env ou edite o script.")
        sys.exit(1)
    app = (
        Application.builder()
        .token(TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )
    app.add_handler(CommandHandler("start", comando_start))
    app.add_handler(CommandHandler(("help", "ajuda", "comandos"), comando_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, processar_mensagem))
    app.add_error_handler(erro_global)
    print(f"GENNIE IA iniciado. Dono: {DONO_ID} | Modelo: {MODEL}")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
