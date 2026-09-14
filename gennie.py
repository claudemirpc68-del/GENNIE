import base64
import io
import json
import logging
import mimetypes
import re
import socket
import sys
import time
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

_lock_socket = None

def garantir_instancia_unica():
    global _lock_socket
    _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _lock_socket.bind(("127.0.0.1", 49876))
    except OSError:
        print("[!] ATENÇÃO: Outra instância do GENNIE Bot já está em execução no sistema. Encerrando processo duplicado.")
        logging.warning("Tentativa de iniciar instância duplicada bloqueada. Porta 49876 já em uso.")
        sys.exit(0)

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
from telegram.ext import Application, CommandHandler, MessageHandler, PicklePersistence, filters

BASE = Path(__file__).resolve().parent
ENV_FILE = BASE / ".env"
CLIENT_SECRET = BASE / "client_secret.json"
TOKEN_FILE = BASE / "token.json"
MEMORIA_FILE = BASE / "gennie_memoria.pickle"
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
MODEL = "openai/gpt-oss-120b"
API_URL = "https://api.groq.com/openai/v1/chat/completions"
BRIDGE_PORT = 8000
BRIDGE_SECRET_KEY = "gennie_bridge_secret_token_2026"


def carregar_env():
    global TOKEN, DONO_ID, API_KEY, MODEL, API_URL, BRIDGE_PORT, BRIDGE_SECRET_KEY
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
            elif linha.startswith("BRIDGE_PORT="):
                val = linha.split("=", 1)[1].strip()
                if val:
                    try:
                        BRIDGE_PORT = int(val)
                    except ValueError:
                        pass
            elif linha.startswith("BRIDGE_SECRET_KEY="):
                val = linha.split("=", 1)[1].strip()
                if val:
                    BRIDGE_SECRET_KEY = val

def autorizado(update: Update):
    if not update.effective_chat:
        return False
    chat_id = str(update.effective_chat.id)
    if chat_id == str(DONO_ID):
        return True
    logging.warning("Tentativa de acesso não autorizado do chat_id: %s (Dono configurado: %s)", chat_id, DONO_ID)
    return False


class GmailAuthExpiredError(Exception):
    """Exceção disparada quando o token OAuth do Gmail expira ou é revogado."""
    pass


def get_gmail_service():
    creds = None
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except Exception:
            creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
            except Exception as e:
                logging.error("Falha ao renovar token OAuth do Gmail: %s", e)
                raise GmailAuthExpiredError("Token do Gmail expirado ou revogado.") from e
        else:
            raise GmailAuthExpiredError("Credenciais válidas do Gmail não encontradas.")
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
        labels = det.get("labelIds", [])
        nao_lido = "UNREAD" in labels
        destacado = "STARRED" in labels
        emails.append({
            "id": det["id"],
            "from": headers.get("from", "?"),
            "subject": headers.get("subject", "(sem assunto)"),
            "date": headers.get("date", ""),
            "unread": nao_lido,
            "starred": destacado,
            "labels": labels,
        })
    return emails


def extrair_corpo_e_anexos(payload):
    corpo = ""
    anexos = []

    def processar_parte(parte):
        nonlocal corpo
        mime = parte.get("mimeType", "")
        filename = parte.get("filename", "")
        body = parte.get("body", {})

        if filename and body.get("attachmentId"):
            anexos.append({
                "filename": filename,
                "mimeType": mime,
                "size": body.get("size", 0),
                "attachmentId": body.get("attachmentId"),
            })
        elif mime == "text/plain" and body.get("data") and not corpo:
            try:
                corpo = base64.urlsafe_b64decode(body["data"]).decode("utf-8", errors="replace")
            except Exception:
                pass

        for subparte in parte.get("parts", []):
            processar_parte(subparte)

    if payload.get("body", {}).get("data") and payload.get("mimeType") == "text/plain":
        try:
            corpo = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
        except Exception:
            pass

    for p in payload.get("parts", []):
        processar_parte(p)

    return corpo, anexos


def ler_email(service, msg_id):
    det = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    payload = det.get("payload", {})
    headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
    corpo, anexos = extrair_corpo_e_anexos(payload)
    
    anexos_formatados = []
    for a in anexos:
        tam_kb = round(a["size"] / 1024, 1)
        anexos_formatados.append(f"{a['filename']} ({tam_kb} KB)")
        
    return {
        "id": det["id"],
        "from": headers.get("from", "?"),
        "subject": headers.get("subject", "(sem assunto)"),
        "date": headers.get("date", ""),
        "body": corpo.strip()[:5000],
        "anexos": anexos_formatados,
    }


def obter_anexo_por_nome(service, msg_id, nome_arquivo=""):
    det = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    _, anexos = extrair_corpo_e_anexos(det.get("payload", {}))
    if not anexos:
        return None, "Nenhum anexo encontrado neste e-mail."
    alvo = None
    if nome_arquivo:
        for a in anexos:
            if nome_arquivo.lower() in a["filename"].lower():
                alvo = a
                break
    if not alvo:
        alvo = anexos[0]
    
    att = service.users().messages().attachments().get(
        userId="me", messageId=msg_id, id=alvo["attachmentId"]
    ).execute()
    dados = base64.urlsafe_b64decode(att.get("data", ""))
    return {"filename": alvo["filename"], "mimeType": alvo["mimeType"], "data": dados}, None


def marcar_lido(service, msg_id):
    service.users().messages().modify(
        userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}
    ).execute()


def arquivar(service, msg_id):
    service.users().messages().modify(
        userId="me", id=msg_id, body={"removeLabelIds": ["INBOX"]}
    ).execute()


def destacar_email(service, msg_id, destacar=True):
    body = {"addLabelIds": ["STARRED"]} if destacar else {"removeLabelIds": ["STARRED"]}
    service.users().messages().modify(userId="me", id=msg_id, body=body).execute()


def lixeira_email(service, msg_id, enviar_lixeira=True):
    if enviar_lixeira:
        service.users().messages().trash(userId="me", id=msg_id).execute()
    else:
        service.users().messages().untrash(userId="me", id=msg_id).execute()


def marcar_spam(service, msg_id):
    service.users().messages().modify(
        userId="me", id=msg_id, body={"addLabelIds": ["SPAM"], "removeLabelIds": ["INBOX"]}
    ).execute()


def obter_ou_criar_etiqueta(service, nome_etiqueta):
    labels_res = service.users().labels().list(userId="me").execute()
    labels = labels_res.get("labels", [])
    for l in labels:
        if l["name"].lower() == nome_etiqueta.lower():
            return l["id"], l["name"]
    nova = service.users().labels().create(
        userId="me",
        body={
            "name": nome_etiqueta,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }
    ).execute()
    return nova["id"], nova["name"]


def aplicar_etiqueta(service, msg_id, nome_etiqueta, remover=False):
    label_id, label_nome = obter_ou_criar_etiqueta(service, nome_etiqueta)
    if remover:
        service.users().messages().modify(
            userId="me", id=msg_id, body={"removeLabelIds": [label_id]}
        ).execute()
        return f"Etiqueta '{label_nome}' removida do e-mail {msg_id}."
    else:
        service.users().messages().modify(
            userId="me", id=msg_id, body={"addLabelIds": [label_id]}
        ).execute()
        return f"Etiqueta '{label_nome}' aplicada com sucesso ao e-mail {msg_id}."


def obter_lote_para_briefing(service, max_emails=8, query="in:inbox is:unread"):
    resultado = service.users().messages().list(
        userId="me", q=query, maxResults=max_emails
    ).execute()
    msgs = resultado.get("messages", [])
    
    # Se não encontrar e-mails não lidos, busca os mais recentes da Inbox
    if not msgs and "is:unread" in query:
        resultado = service.users().messages().list(
            userId="me", q="in:inbox", maxResults=max_emails
        ).execute()
        msgs = resultado.get("messages", [])
        
    emails_lote = []
    for m in msgs:
        det = service.users().messages().get(
            userId="me", id=m["id"], format="full"
        ).execute()
        payload = det.get("payload", {})
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
        labels = det.get("labelIds", [])
        corpo, anexos = extrair_corpo_e_anexos(payload)
        
        snippet = det.get("snippet", "")
        corpo_resumo = (corpo or snippet or "").strip()[:600]
        
        emails_lote.append({
            "id": det["id"],
            "threadId": det.get("threadId"),
            "from": headers.get("from", "?"),
            "subject": headers.get("subject", "(sem assunto)"),
            "date": headers.get("date", ""),
            "unread": "UNREAD" in labels,
            "starred": "STARRED" in labels,
            "tem_anexos": len(anexos) > 0,
            "qtd_anexos": len(anexos),
            "trecho": corpo_resumo,
        })
    return emails_lote


def obter_thread_completa(service, msg_id):
    det = service.users().messages().get(userId="me", id=msg_id, format="minimal").execute()
    thread_id = det.get("threadId", msg_id)
    
    thread = service.users().threads().get(userId="me", id=thread_id, format="full").execute()
    mensagens = thread.get("messages", [])
    
    historico = []
    for m in mensagens:
        payload = m.get("payload", {})
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
        corpo, anexos = extrair_corpo_e_anexos(payload)
        historico.append({
            "id": m["id"],
            "from": headers.get("from", "?"),
            "date": headers.get("date", ""),
            "subject": headers.get("subject", ""),
            "corpo": (corpo or "").strip()[:2000],
            "qtd_anexos": len(anexos),
        })
    return {
        "threadId": thread_id,
        "total_mensagens": len(historico),
        "mensagens": historico,
    }


def formatar_corpo_com_assinatura(corpo: str) -> str:
    texto = (corpo or "").strip()
    if not texto:
        return ASSINATURA
    primeiro_nome = ASSINATURA.split()[0]
    padroes_nome = [
        re.escape(ASSINATURA),
        re.escape(primeiro_nome),
        r"Claudemir\s+Pedroso",
        r"Claudemir\s+Cubas",
    ]
    padrao_re = r"(?i)(?:[\r\n\s]+)(?:" + "|".join(padroes_nome) + r")\s*$"
    texto_limpo = re.sub(padrao_re, "", texto).strip()
    
    despedidas = [
        "atenciosamente,", "atenciosamente", 
        "cordialmente,", "cordialmente", 
        "abraços,", "abraços", "abracos,", "abracos", 
        "obrigado,", "grato,", "respeitosamente,"
    ]
    linhas = texto_limpo.splitlines()
    ultima_linha = linhas[-1].strip().lower() if linhas else ""
    if any(ultima_linha == d for d in despedidas) or ultima_linha.endswith(","):
        return f"{texto_limpo}\n{ASSINATURA}"
    return f"{texto_limpo}\n\n{ASSINATURA}"


def enviar_email(service, dest, assunto, corpo, anexo_bytes=None, anexo_nome=None):
    corpo_completo = formatar_corpo_com_assinatura(corpo)
    if anexo_bytes and anexo_nome:
        msg = MIMEMultipart()
        msg["To"] = dest
        msg["From"] = CONTA
        msg["Subject"] = assunto
        msg.attach(MIMEText(corpo_completo, "plain", "utf-8"))
        
        tipo_mime, _ = mimetypes.guess_type(anexo_nome)
        tipo_mime = tipo_mime or "application/octet-stream"
        main_type, sub_type = tipo_mime.split("/", 1) if "/" in tipo_mime else ("application", "octet-stream")
        
        parte_anexo = MIMEBase(main_type, sub_type)
        parte_anexo.set_payload(anexo_bytes)
        encoders.encode_base64(parte_anexo)
        parte_anexo.add_header("Content-Disposition", f'attachment; filename="{anexo_nome}"')
        msg.attach(parte_anexo)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    else:
        m = MIMEText(corpo_completo, "plain", "utf-8")
        m["To"] = dest
        m["From"] = CONTA
        m["Subject"] = assunto
        raw = base64.urlsafe_b64encode(m.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


def responder_email(service, msg_id, corpo, anexo_bytes=None, anexo_nome=None):
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
    
    if anexo_bytes and anexo_nome:
        msg = MIMEMultipart()
        msg["To"] = dest
        msg["From"] = CONTA
        msg["Subject"] = assunto
        msg["In-Reply-To"] = msgid
        msg["References"] = refs
        msg.attach(MIMEText(corpo_completo, "plain", "utf-8"))
        
        tipo_mime, _ = mimetypes.guess_type(anexo_nome)
        tipo_mime = tipo_mime or "application/octet-stream"
        main_type, sub_type = tipo_mime.split("/", 1) if "/" in tipo_mime else ("application", "octet-stream")
        
        parte_anexo = MIMEBase(main_type, sub_type)
        parte_anexo.set_payload(anexo_bytes)
        encoders.encode_base64(parte_anexo)
        parte_anexo.add_header("Content-Disposition", f'attachment; filename="{anexo_nome}"')
        msg.attach(parte_anexo)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    else:
        m = MIMEText(corpo_completo, "plain", "utf-8")
        m["To"] = dest
        m["From"] = CONTA
        m["Subject"] = assunto
        m["In-Reply-To"] = msgid
        m["References"] = refs
        raw = base64.urlsafe_b64encode(m.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return dest, assunto


SYSTEM_PROMPT = f"""Você é GENNIE, assistente pessoal executiva de elite dedicada ao seu desenvolvedor e senhor, Claudemir Pedroso Cubas, atendendo via Telegram.

IDENTIDADE & PERSONALIDADE (Mordomo Executivo de Elite)
- Persona: Inspirada na sofisticação, cortesia e extrema eficiência de um mordomo executivo de alta classe (estilo Jarvis / Alta Classe).
- Postura: Altamente respeitosa, polida, solícita e impecavelmente pontual.
- Tratamento: Trate o Claudemir com deferência cordial ("Sr. Claudemir" ou "senhor").
- Tom de Voz: Comunicação direta, elegante e sem rodeios. Destaque fatos, métricas e decisões com clareza cristalina.
- Conta de E-mail gerenciada: {CONTA}
- Assinatura oficial de e-mail: {ASSINATURA} (o sistema anexa automaticamente. Jamais duplique a assinatura manual ao redigir).

COMUNICAÇÃO & RELACIONAMENTO
- Responda sempre em português do Brasil (pt-BR) com elegância e cordialidade natural.
- Saudações: Sempre responda calorosa e educadamente a cumprimentos ("oi", "olá", "bom dia", "boa tarde"). Ex: "Às suas ordens, Sr. Claudemir. Como posso servi-lo neste momento?"
- Agradecimentos: Receba elogios e agradecimentos com modéstia refinada (ex: "É uma honra servi-lo, senhor", "Sempre à sua total disposição").
- Proatividade controlada: Após concluir uma solicitação, indique discretamente que permanece a postos para o próximo passo.

ESCOPO DE ATUAÇÃO
1. Gestão e Curadoria de E-mails (Gmail): Triagem, briefings executivos, respostas com prévia obrigatória e gestão de anexos.
2. Auditoria e Higienização de Arquivos (Pasta Downloads): Supervisão, interpretação de relatórios e notificação de limpezas realizadas pelo Agente Local de Downloads (especialmente na rotina agendada das 18:00).

DIRETRIZES PARA AVISOS DA PASTA DOWNLOADS
Quando receber dados brutos, logs ou relatórios do Agente de Downloads (ou quando o usuário perguntar sobre downloads):
- Transforme os dados técnicos em um comunicado executivo limpo e agradável.
- Estrutura recomendada do informe:
  🎩 **Relatório de Manutenção — Pasta Downloads**
  • Cumprimento cortês ao Sr. Claudemir.
  • Resumo quantitativo: arquivos classificados por categoria (Documentos, Instaladores, Mídias, etc.).
  • Higienização: quantidade de arquivos duplicados descartados e temporários antigos limpos.
  • Eficiência: espaço em disco recuperado (em MB ou GB).
  • Conclusão refinada assegurando que o diretório está em perfeita ordem.

REGRAS OBRIGATÓRIAS
1. Segurança Estrita em E-mails: NUNCA envie ou responda qualquer e-mail sem antes apresentar a prévia e aguardar confirmação explícita do Sr. Claudemir.
2. Fidelidade aos Fatos: Jamais invente IDs, arquivos ou métricas. Use estritamente os dados reais fornecidos pelas ferramentas e relatórios.
3. Discrição e Foco: Evite respostas excessivamente longas ou prolixas quando um resumo pontual e estruturado for mais eficiente.

CAPACIDADES
- listar_emails: busca e-mails (caixa de entrada, não lidos, por remetente/assunto, com anexos ou estrelas).
- ler_email: lê o conteúdo completo de um e-mail pelo ID e lista os anexos disponíveis.
- gerar_briefing: analisa os e-mails recentes/não lidos em lote e gera um relatório executivo consolidado.
- resumir_thread: sintetiza o histórico completo de trocas de mensagens de uma conversa pelo ID.
- baixar_anexo: faz o download de um anexo e envia diretamente para o usuário no Telegram.
- enviar_email: cria um e-mail novo (exigindo aprovação com prévia antes do envio).
- responder_email: responde a um e-mail existente (exigindo aprovação antes do envio).
- destacar_email: marca ou desmarca um e-mail com estrela.
- lixeira_email: move um e-mail para a lixeira do Gmail ou restaura-o.
- marcar_spam: move um e-mail indesejado para a pasta de Spam.
- aplicar_etiqueta: cria, aplica ou remove etiquetas/marcadores customizados em um e-mail.
- marcar_lido / arquivar: organizam a caixa de entrada.
- limpar_memoria: limpa o histórico de contexto.

ESTRUTURA DE RESPOSTA DO BRIEFING DE E-MAILS
Ao solicitar briefing ou resumo de mensagens:
  📊 **Panorama Geral da Caixa Postal**
  🔥 **Urgências, Prazos & Decisões** (quem enviou e a ação requerida)
  ℹ️ **Informativos Relevantes**
  💡 **Próximos Passos Sugeridos pelo Assistente**

EXEMPLOS DE INTERAÇÃO
- "oi" → "Às suas ordens, Sr. Claudemir. Como posso servi-lo hoje?"
- "como estão meus downloads?" → "A pasta Downloads é monitorada pelo Agente Autônomo com higienização diária às 18:00, senhor. Posso conferir o último relatório caso deseje."
- "relatório de downloads recebido: 12 arquivos movidos, 3 duplicados apagados, 210MB liberados" →
  "🎩 **Relatório de Higienização — Pasta Downloads**
  Boa tarde, Sr. Claudemir. A rotina das 18:00 foi concluída com êxito:
  📂 **12 arquivos** devidamente organizados por categoria.
  🗑️ **3 arquivos duplicados** eliminados.
  💾 **210 MB de espaço recuperado** em seu armazenamento.
  Tudo devidamente organizado e pronto para uso, senhor."
- "obrigado GENNIE" → "É um privilégio auxiliá-lo, senhor. Se precisar de algo mais, estou sempre à sua total disposição."
"""


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "listar_emails",
            "description": "Lista e-mails da conta (por padrão a caixa de entrada). Suporta filtros como 'in:inbox', 'has:attachment', 'is:starred', 'filename:pdf', 'from:alguem@x.com'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Filtro Gmail, ex: 'in:inbox', 'has:attachment', 'is:starred', 'is:unread', 'from:...', 'subject:...'."},
                    "max_results": {"type": "integer", "description": "Quantidade máxima (padrão 5)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gerar_briefing",
            "description": "Coleta múltiplos e-mails recentes ou não lidos da caixa de entrada em lote para gerar um briefing executivo consolidado com prioridades, prazos e ações.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Filtro de busca (padrão: 'in:inbox is:unread' ou 'in:inbox')."},
                    "max_emails": {"type": "integer", "description": "Quantidade de e-mails para consolidar no briefing (padrão 8)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resumir_thread",
            "description": "Obtém a thread completa de trocas de mensagens de uma conversa ou e-mail específico pelo ID para sintetizar o histórico e decisões.",
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
            "name": "ler_email",
            "description": "Lê o conteúdo completo de um e-mail pelo ID e retorna o corpo e a lista de anexos disponíveis.",
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
            "name": "baixar_anexo",
            "description": "Baixa um anexo do Gmail e envia o arquivo diretamente para o usuário no Telegram.",
            "parameters": {
                "type": "object",
                "properties": {
                    "msg_id": {"type": "string", "description": "ID do e-mail que contém o anexo."},
                    "nome_arquivo": {"type": "string", "description": "Nome ou parte do nome do arquivo desejado (opcional se houver apenas um anexo)."},
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
            "name": "destacar_email",
            "description": "Adiciona ou remove a estrela (destaque) de um e-mail no Gmail.",
            "parameters": {
                "type": "object",
                "properties": {
                    "msg_id": {"type": "string", "description": "ID do e-mail."},
                    "destacar": {"type": "boolean", "description": "True para destacar com estrela, False para remover."},
                },
                "required": ["msg_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lixeira_email",
            "description": "Move um e-mail para a lixeira do Gmail ou o restaura.",
            "parameters": {
                "type": "object",
                "properties": {
                    "msg_id": {"type": "string", "description": "ID do e-mail."},
                    "enviar_lixeira": {"type": "boolean", "description": "True para mover para lixeira, False para restaurar."},
                },
                "required": ["msg_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "marcar_spam",
            "description": "Move um e-mail para a pasta de Spam do Gmail.",
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
            "name": "aplicar_etiqueta",
            "description": "Cria, aplica ou remove uma etiqueta customizada em um e-mail no Gmail.",
            "parameters": {
                "type": "object",
                "properties": {
                    "msg_id": {"type": "string", "description": "ID do e-mail."},
                    "nome_etiqueta": {"type": "string", "description": "Nome da etiqueta (ex: 'Finanças', 'Projetos', 'Trabalho')."},
                    "remover": {"type": "boolean", "description": "True para remover a etiqueta, False para aplicar."},
                },
                "required": ["msg_id", "nome_etiqueta"],
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
    {
        "type": "function",
        "function": {
            "name": "limpar_memoria",
            "description": "Limpa e reseta a memória de conversas e quaisquer rascunhos pendentes. Use sempre que o usuário pedir para limpar a memória, apagar o histórico, esquecer a conversa ou resetar.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    }
]


def chamar_deepseek(messages, tools=None, tool_choice="auto", max_retries=3):
    body = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.2,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = tool_choice
    
    for tentativa in range(max_retries):
        try:
            r = httpx.post(
                API_URL,
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json=body,
                timeout=120,
            )
            if r.status_code == 429 and tentativa < max_retries - 1:
                tempo_espera = 5.0
                try:
                    retry_header = r.headers.get("retry-after")
                    if retry_header:
                        tempo_espera = float(retry_header) + 0.5
                except Exception:
                    pass
                time.sleep(tempo_espera)
                continue
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and tentativa < max_retries - 1:
                tempo_espera = 5.0
                try:
                    retry_header = e.response.headers.get("retry-after")
                    if retry_header:
                        tempo_espera = float(retry_header) + 0.5
                except Exception:
                    pass
                time.sleep(tempo_espera)
                continue
            raise



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
            marcas = []
            if e.get("unread"):
                marcas.append("🔴 NÃO LIDO")
            if e.get("starred"):
                marcas.append("⭐ DESTACADO")
            tag_status = f" [{', '.join(marcas)}]" if marcas else ""
            linhas.append(f"ID: {e['id']}{tag_status}\nDe: {e['from']}\nAssunto: {e['subject']}\nData: {e['date']}")
        return json.dumps({"emails": linhas}, ensure_ascii=False)

    if name == "gerar_briefing":
        query = arguments.get("query", "in:inbox is:unread")
        max_emails = int(arguments.get("max_emails", 8))
        lote = obter_lote_para_briefing(service, max_emails=max_emails, query=query)
        if not lote:
            return json.dumps({"resultado": "Nenhum e-mail recente encontrado para o briefing."}, ensure_ascii=False)
        return json.dumps({"total_analisados": len(lote), "emails": lote}, ensure_ascii=False)

    if name == "resumir_thread":
        thread_info = obter_thread_completa(service, arguments["msg_id"])
        return json.dumps(thread_info, ensure_ascii=False)

    if name == "ler_email":
        email = ler_email(service, arguments["msg_id"])
        return json.dumps(email, ensure_ascii=False)

    if name == "baixar_anexo":
        anexo, erro = obter_anexo_por_nome(service, arguments["msg_id"], arguments.get("nome_arquivo", ""))
        if erro or not anexo:
            return json.dumps({"erro": erro or "Não foi possível obter o anexo."}, ensure_ascii=False)
        user_data["anexo_para_enviar_tg"] = anexo
        return json.dumps({
            "resultado": f"Anexo '{anexo['filename']}' baixado com sucesso do Gmail e pronto para envio ao usuário no Telegram.",
            "filename": anexo["filename"],
            "mimeType": anexo["mimeType"]
        }, ensure_ascii=False)

    if name == "enviar_email":
        corpo_final = formatar_corpo_com_assinatura(arguments.get("corpo", ""))
        anexo_pendente = user_data.get("anexo_pendente")
        anexo_nome = anexo_pendente["nome"] if anexo_pendente else None
        anexo_bytes = anexo_pendente["bytes"] if anexo_pendente else None
        
        user_data["draft"] = {
            "acao": "enviar",
            "dest": arguments["dest"],
            "assunto": arguments.get("assunto", ""),
            "corpo": corpo_final,
            "anexo_nome": anexo_nome,
            "anexo_bytes": anexo_bytes,
        }
        
        info_anexo = f"\n📎 Anexo: {anexo_nome} ({round(anexo_pendente['tamanho']/1024, 1)} KB)" if anexo_pendente else ""
        return json.dumps({
            "acao": "PEDIR_APROVACAO",
            "msg": (
                f"Prévia do e-mail:\nPara: {arguments['dest']}\nAssunto: {arguments.get('assunto','')}{info_anexo}\n\n"
                f"Mensagem:\n{corpo_final}\n\nResponda 'sim' para enviar ou 'cancelar'."
            ),
        }, ensure_ascii=False)

    if name == "responder_email":
        corpo_final = formatar_corpo_com_assinatura(arguments.get("corpo", ""))
        anexo_pendente = user_data.get("anexo_pendente")
        anexo_nome = anexo_pendente["nome"] if anexo_pendente else None
        anexo_bytes = anexo_pendente["bytes"] if anexo_pendente else None
        
        user_data["draft"] = {
            "acao": "responder",
            "msg_id": arguments["msg_id"],
            "corpo": corpo_final,
            "anexo_nome": anexo_nome,
            "anexo_bytes": anexo_bytes,
        }
        
        info_anexo = f"\n📎 Anexo: {anexo_nome} ({round(anexo_pendente['tamanho']/1024, 1)} KB)" if anexo_pendente else ""
        return json.dumps({
            "acao": "PEDIR_APROVACAO",
            "msg": (
                f"Prévia da resposta ao e-mail {arguments['msg_id']}:{info_anexo}\n\n{corpo_final}\n\n"
                f"Responda 'sim' para enviar ou 'cancelar'."
            ),
        }, ensure_ascii=False)

    if name == "destacar_email":
        destacar = arguments.get("destacar", True)
        destacar_email(service, arguments["msg_id"], destacar=destacar)
        status_txt = "destacado com estrela ⭐" if destacar else "com estrela removida"
        return json.dumps({"resultado": f"E-mail {arguments['msg_id']} {status_txt} com sucesso."}, ensure_ascii=False)

    if name == "lixeira_email":
        enviar = arguments.get("enviar_lixeira", True)
        lixeira_email(service, arguments["msg_id"], enviar_lixeira=enviar)
        status_txt = "movido para a Lixeira 🗑️" if enviar else "restaurado da Lixeira"
        return json.dumps({"resultado": f"E-mail {arguments['msg_id']} {status_txt} com sucesso."}, ensure_ascii=False)

    if name == "marcar_spam":
        marcar_spam(service, arguments["msg_id"])
        return json.dumps({"resultado": f"E-mail {arguments['msg_id']} marcado como SPAM 🚫 e removido da caixa de entrada."}, ensure_ascii=False)

    if name == "aplicar_etiqueta":
        remover = arguments.get("remover", False)
        res_etiqueta = aplicar_etiqueta(service, arguments["msg_id"], arguments["nome_etiqueta"], remover=remover)
        return json.dumps({"resultado": res_etiqueta}, ensure_ascii=False)

    if name == "marcar_lido":
        marcar_lido(service, arguments["msg_id"])
        return json.dumps({"resultado": f"E-mail {arguments['msg_id']} marcado como lido."}, ensure_ascii=False)

    if name == "arquivar":
        arquivar(service, arguments["msg_id"])
        return json.dumps({"resultado": f"E-mail {arguments['msg_id']} arquivado."}, ensure_ascii=False)

    if name == "limpar_memoria":
        user_data.clear()
        return json.dumps({
            "resultado": "Memória de contexto e rascunhos pendentes limpa com sucesso no sistema. Confirme ao usuário que a memória foi zerada e coloque-se à disposição para um novo assunto."
        }, ensure_ascii=False)

    return json.dumps({"erro": "Ferramenta desconhecida."}, ensure_ascii=False)


def confirmar_e_envio(service, draft):
    anexo_bytes = draft.get("anexo_bytes")
    anexo_nome = draft.get("anexo_nome")
    anexo_str = f" com o anexo '{anexo_nome}'" if anexo_nome else ""

    if draft["acao"] == "enviar":
        enviar_email(service, draft["dest"], draft["assunto"], draft["corpo"], anexo_bytes=anexo_bytes, anexo_nome=anexo_nome)
        return f"✅ Pronto! E-mail enviado com sucesso para {draft['dest']}{anexo_str} | Assunto: '{draft['assunto']}'.\n\nSe precisar de mais alguma coisa, é só falar! 😊"
    if draft["acao"] == "responder":
        dest, assunto = responder_email(service, draft["msg_id"], draft["corpo"], anexo_bytes=anexo_bytes, anexo_nome=anexo_nome)
        return f"✅ Resposta enviada com sucesso para {dest}{anexo_str} | Assunto: '{assunto}'!\n\nPosso te ajudar com mais algum e-mail?"
    return "Nada pendente para envio."


async def comando_start(update: Update, context):
    if not autorizado(update):
        return
    logging.info("Comando /start recebido de %s", update.effective_chat.id)
    await update.message.reply_text(
        "Olá! Sou o GENNIE, seu assistente de e-mail com IA. 😊\n\n"
        "Pode pedir com palavras simples, por exemplo:\n"
        "📬 \"veja meus emails\"\n"
        "⭐ \"emails com estrela\" ou \"destaque o email <id>\"\n"
        "📎 \"baixe o anexo do email <id>\"\n"
        "🏷️ \"coloque a etiqueta Finanças no email <id>\"\n"
        "🗑️ \"mova o email de propaganda para a lixeira\"\n"
        "🚫 \"marque este email como spam\"\n"
        "✉️ \"responda o email sobre...\"\n"
        "🆕 \"envie um email para <email>: assunto e mensagem\"\n"
        "📎 Ou envie um documento/foto aqui no chat para anexar!\n"
        "🧹 /limpar - Reseta a memória do diálogo atual"
    )


async def processar_mensagem(update: Update, context):
    if not autorizado(update):
        return
    texto = update.message.text.strip() if update.message.text else ""
    if not texto:
        return
        
    logging.info("Mensagem recebida de %s: '%s'", update.effective_chat.id, texto)
    t = texto.lower()

    if not API_KEY:
        await update.message.reply_text("DeepSeek API não configurada.")
        return

    # Atalho rápido para solicitações de limpeza de memória em linguagem natural
    termos_limpeza = [
        "limpar memória", "limpar memoria", "limpa memória", "limpa memoria", "limpe a memória", "limpe a memoria",
        "resetar memória", "resetar memoria", "resetar", "apagar memória", "apagar memoria", "apague a memória",
        "apagar histórico", "apagar historico", "apague o histórico", "apague o historico",
        "limpar histórico", "limpar historico", "limpa o histórico", "limpa o historico",
        "esquecer tudo", "esquecer conversa", "esqueça tudo", "esqueça a conversa",
        "limpar contexto", "limpa o contexto", "zerar memória", "zerar memoria", "zere a memória",
    ]
    if any(t == termo or t.startswith(termo) for termo in termos_limpeza):
        context.user_data.clear()
        msg_confirmacao = (
            "🧹 *Confirmação de Limpeza de Memória*\n\n"
            "✅ O histórico de conversas anteriores foi apagado.\n"
            "✅ Quaisquer rascunhos de e-mail pendentes foram cancelados.\n"
            "💾 O arquivo de persistência em disco foi atualizado.\n\n"
            "Tudo pronto para começarmos do zero! Em que posso te ajudar hoje? 😊"
        )
        await update.message.reply_text(msg_confirmacao, parse_mode="Markdown")
        return

    try:
        service = get_gmail_service()
    except GmailAuthExpiredError:
        msg_auth = (
            "⚠️ *Atenção, Sr. Claudemir: Autorização do Gmail Necessária*

"
            "As credenciais de acesso ao seu Gmail expiraram ou foram revogadas pelo Google.

"
            "👉 Para renovar com 1 clique, execute no seu computador o arquivo:
"
            "`C:\Users\FAMÍLIA\Desktop\GENNIE_BOT\RENOVAR_GMAIL.bat`

"
            "Basta fazer o login no navegador e clicar em *Permitir*. Assim que concluir, estarei pronta para ler e gerenciar seus e-mails imediatamente! 🎩✨"
        )
        await update.message.reply_text(msg_auth, parse_mode="Markdown")
        return
    except Exception as e:
        logging.exception("Erro ao inicializar serviço do Gmail: %s", e)
        await update.message.reply_text(f"⚠️ Erro ao conectar ao Gmail: {e}")
        return

    draft = context.user_data.get("draft")
    if draft:
        if t in ("sim", "confirmo", "pode enviar", "pode mandar", "sim, envie", "sim, pode enviar", "ok", "manda", "envia"):
            try:
                resultado = confirmar_e_envio(service, draft)
            except Exception as e:
                resultado = f"Ops, ocorreu um erro ao enviar o e-mail: {e}"
            context.user_data.pop("draft", None)
            context.user_data.pop("anexo_pendente", None)
            
            # Mantém histórico para continuidade da conversa
            hist = context.user_data.get("hist", [])
            hist.append({"role": "user", "content": texto})
            hist.append({"role": "assistant", "content": resultado})
            context.user_data["hist"] = hist[-20:]
            
            await update.message.reply_text(resultado)
            return

        if "cancelar" in t or "não" in t or "cancela" in t:
            context.user_data.pop("draft", None)
            context.user_data.pop("anexo_pendente", None)
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

    # Envia arquivo anexo baixado do Gmail diretamente para o chat do Telegram, se houver
    anexo_tg = context.user_data.pop("anexo_para_enviar_tg", None)
    if anexo_tg:
        try:
            await update.message.reply_document(
                document=io.BytesIO(anexo_tg["data"]),
                filename=anexo_tg["filename"],
                caption=f"📎 Aqui está o arquivo: *{anexo_tg['filename']}*",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.exception("Erro ao enviar anexo no Telegram")
            await update.message.reply_text(f"Baixei o arquivo '{anexo_tg['filename']}', mas houve um erro ao enviar para o Telegram: {e}")


async def receber_documento(update: Update, context):
    if not autorizado(update):
        return
    doc = update.message.document
    photo = update.message.photo
    caption = update.message.caption or ""

    if doc:
        file = await doc.get_file()
        file_bytes = await file.download_as_bytearray()
        file_name = doc.file_name or "documento.pdf"
        file_size = len(file_bytes)
    elif photo:
        foto = photo[-1]
        file = await foto.get_file()
        file_bytes = await file.download_as_bytearray()
        file_name = f"foto_{update.message.message_id}.jpg"
        file_size = len(file_bytes)
    else:
        return

    context.user_data["anexo_pendente"] = {
        "nome": file_name,
        "bytes": bytes(file_bytes),
        "tamanho": file_size,
    }

    tam_kb = round(file_size / 1024, 1)

    if caption.strip():
        await update.message.reply_text(
            f"📎 *Arquivo `{file_name}` ({tam_kb} KB) recebido!*\nProcessando instruções...",
            parse_mode="Markdown"
        )
        update.message.text = caption
        await processar_mensagem(update, context)
    else:
        await update.message.reply_text(
            f"📎 *Arquivo recebido com sucesso!*\n\n"
            f"📄 *Nome:* `{file_name}`\n"
            f"📊 *Tamanho:* {tam_kb} KB\n\n"
            f"O que você deseja fazer com este anexo?\n"
            f"💡 *Exemplo:* \"Envie este arquivo para contato@exemplo.com com o assunto Documento e mensagem Segue em anexo.\"",
            parse_mode="Markdown"
        )


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


async def comando_limpar(update: Update, context):
    if not autorizado(update):
        return
    context.user_data.clear()
    msg_confirmacao = (
        "🧹 *Confirmação de Limpeza de Memória*\n\n"
        "✅ O histórico de conversas anteriores foi apagado.\n"
        "✅ Quaisquer rascunhos de e-mail pendentes foram cancelados.\n"
        "💾 O arquivo de persistência em disco foi atualizado.\n\n"
        "Tudo pronto para começarmos do zero! Em que posso te ajudar hoje? 😊"
    )
    await update.message.reply_text(msg_confirmacao, parse_mode="Markdown")


async def comando_briefing(update: Update, context):
    if not autorizado(update):
        return
    update.message.text = "Por favor, elabore um briefing executivo completo e estruturado dos meus e-mails mais recentes."
    await processar_mensagem(update, context)


async def post_init_bridge(application) -> None:
    """Inicializa o Bridge REST Server assíncrono para integrações externas."""
    try:
        import bridge_server
        await bridge_server.iniciar_servidor_bridge(port=BRIDGE_PORT)
        logging.info("Bridge REST da GENNIE inicializado com sucesso na porta %s", BRIDGE_PORT)
    except Exception as e:
        logging.warning("Não foi possível iniciar Bridge REST Server da GENNIE: %s", e)


def main():
    logging.basicConfig(level=logging.INFO)
    garantir_instancia_unica()
    carregar_env()
    if not TOKEN:
        print("TELEGRAM_TOKEN não configurado. Adicione ao .env ou edite o script.")
        sys.exit(1)
    
    persistencia = PicklePersistence(filepath=str(MEMORIA_FILE))
    app = (
        Application.builder()
        .token(TOKEN)
        .persistence(persistencia)
        .post_init(post_init_bridge)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )
    app.add_handler(CommandHandler("start", comando_start))
    app.add_handler(CommandHandler(("help", "ajuda", "comandos"), comando_start))
    app.add_handler(CommandHandler(("limpar", "reset", "esquecer"), comando_limpar))
    app.add_handler(CommandHandler(("briefing", "resumo", "resumos"), comando_briefing))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, processar_mensagem))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, receber_documento))
    app.add_error_handler(erro_global)
    print(f"GENNIE IA iniciado com Persistência Ativa & Bridge REST (Porta {BRIDGE_PORT}). Dono: {DONO_ID} | Modelo: {MODEL}")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()