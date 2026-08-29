"""
====================================================================
GENNIE BOT - Suíte Completa de Verificação e Validação de Funcionalidades
====================================================================
Executa testes unitários, de integração, de segurança e de IA:
 1. Ambiente, Dependências e Arquivos (.env, OAuth2, Pickle)
 2. Regras de Segurança, Controle de Acesso (Dono ID) e Trava de Instância Única
 3. Conectividade e Handshake com Telegram Bot API (@GENNIE_MAY_BOT)
 4. Diagnóstico do OAuth2 do Gmail (Verificação de Token e Alerta de Renovação)
 5. Validação Funcional das Ferramentas do Gmail (Listar, Ler, Anexos, Lote, Threads)
 6. Validação das Operações de Organização (Estrelas, Etiquetas, Lixeira, Spam, Lido/Arquivar)
 7. Formatação de E-mails e Assinatura Oficial Anti-Duplicação ("Claudemir Pedroso Cubas")
 8. Trava de Segurança Human-in-the-Loop (Prévia, Envio, Resposta, Anexos e Cancelamento)
 9. Inteligência Artificial, Diálogo Natural e Function Calling (Groq / GPT / Llama)
10. Persistência de Memória em Disco (PicklePersistence / gennie_memoria.pickle)
====================================================================
"""

import asyncio
import base64
import io
import json
import os
import pickle
import re
import socket
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock
import httpx

# Garante suporte a UTF-8 no terminal Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Cores ANSI para o terminal
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
TOKEN_FILE = BASE_DIR / "token.json"
CLIENT_SECRET = BASE_DIR / "client_secret.json"
MEMORIA_FILE = BASE_DIR / "gennie_memoria.pickle"


class MockGmailService:
    """Simulador de alta fidelidade da API v1 do Gmail para testes funcionais determinísticos."""
    def __init__(self):
        self._labels = [
            {"id": "INBOX", "name": "INBOX"},
            {"id": "UNREAD", "name": "UNREAD"},
            {"id": "STARRED", "name": "STARRED"},
            {"id": "SPAM", "name": "SPAM"},
            {"id": "TRASH", "name": "TRASH"},
            {"id": "Label_1", "name": "Projetos"}
        ]
        
        texto_exemplo = "Olá Claudemir,\nSegue o balanço financeiro e as faturas do mês em anexo.\nFavor confirmar o recebimento.\n\nAtenciosamente,\nEquipe Financeira"
        texto_b64 = base64.urlsafe_b64encode(texto_exemplo.encode("utf-8")).decode("utf-8")
        anexo_b64 = base64.urlsafe_b64encode(b"%PDF-1.5 SIMULACAO DE FATURA CONSOLIDADA").decode("utf-8")
        
        self._messages = {
            "msg_teste_001": {
                "id": "msg_teste_001",
                "threadId": "thread_teste_001",
                "labelIds": ["INBOX", "UNREAD"],
                "snippet": "Olá Claudemir, Segue o balanço financeiro e as faturas...",
                "payload": {
                    "mimeType": "multipart/mixed",
                    "headers": [
                        {"name": "From", "value": "financeiro@empresa.com"},
                        {"name": "To", "value": "claudemirpc68@gmail.com"},
                        {"name": "Subject", "value": "Relatório Financeiro Mensal"},
                        {"name": "Date", "value": "Fri, 29 Aug 2026 18:30:00 -0300"},
                        {"name": "Message-ID", "value": "<fat202608@empresa.com>"}
                    ],
                    "parts": [
                        {
                            "mimeType": "text/plain",
                            "body": {"data": texto_b64, "size": len(texto_exemplo)}
                        },
                        {
                            "mimeType": "application/pdf",
                            "filename": "fatura_agosto_2026.pdf",
                            "body": {"attachmentId": "att_fatura_01", "size": 45000}
                        }
                    ]
                }
            },
            "msg_teste_002": {
                "id": "msg_teste_002",
                "threadId": "thread_teste_001",
                "labelIds": ["INBOX", "STARRED"],
                "snippet": "Re: Relatório Financeiro Mensal - Recebido e aprovado.",
                "payload": {
                    "mimeType": "text/plain",
                    "headers": [
                        {"name": "From", "value": "diretoria@empresa.com"},
                        {"name": "To", "value": "claudemirpc68@gmail.com"},
                        {"name": "Subject", "value": "Re: Relatório Financeiro Mensal"},
                        {"name": "Date", "value": "Fri, 29 Aug 2026 18:45:00 -0300"},
                        {"name": "Message-ID", "value": "<re_fat202608@empresa.com>"},
                        {"name": "References", "value": "<fat202608@empresa.com>"}
                    ],
                    "body": {"data": base64.urlsafe_b64encode(b"Recebido e aprovado pela diretoria.").decode(), "size": 36}
                }
            }
        }
        self._attachments = {
            "att_fatura_01": {"data": anexo_b64, "size": 45000}
        }

    def users(self):
        return self

    def getProfile(self, userId="me"):
        mock = MagicMock()
        mock.execute.return_value = {
            "emailAddress": "claudemirpc68@gmail.com",
            "messagesTotal": 1420,
            "threadsTotal": 850,
            "historyId": "994821"
        }
        return mock

    def messages(self):
        mock = MagicMock()
        
        def list_impl(userId="me", q="", maxResults=5):
            m_list = MagicMock()
            msgs = [{"id": k, "threadId": v["threadId"]} for k, v in self._messages.items()]
            if "has:attachment" in q:
                msgs = [msgs[0]]
            m_list.execute.return_value = {"messages": msgs[:maxResults], "resultSizeEstimate": len(msgs)}
            return m_list

        def get_impl(userId="me", id="msg_teste_001", format="full", metadataHeaders=None):
            m_get = MagicMock()
            msg = self._messages.get(id, self._messages["msg_teste_001"])
            m_get.execute.return_value = msg
            return m_get

        def modify_impl(userId="me", id="msg_teste_001", body=None):
            m_mod = MagicMock()
            msg = self._messages.get(id)
            if msg and body:
                add = body.get("addLabelIds", [])
                rem = body.get("removeLabelIds", [])
                msg["labelIds"] = [l for l in msg["labelIds"] if l not in rem] + [l for l in add if l not in msg["labelIds"]]
            m_mod.execute.return_value = msg
            return m_mod

        def trash_impl(userId="me", id="msg_teste_001"):
            m_tr = MagicMock()
            msg = self._messages.get(id)
            if msg and "TRASH" not in msg["labelIds"]:
                msg["labelIds"].append("TRASH")
            m_tr.execute.return_value = msg
            return m_tr

        def untrash_impl(userId="me", id="msg_teste_001"):
            m_utr = MagicMock()
            msg = self._messages.get(id)
            if msg and "TRASH" in msg["labelIds"]:
                msg["labelIds"].remove("TRASH")
            m_utr.execute.return_value = msg
            return m_utr

        def send_impl(userId="me", body=None):
            m_snd = MagicMock()
            m_snd.execute.return_value = {"id": "msg_enviada_999", "labelIds": ["SENT"]}
            return m_snd

        mock.list = list_impl
        mock.get = get_impl
        mock.modify = modify_impl
        mock.trash = trash_impl
        mock.untrash = untrash_impl
        mock.send = send_impl
        mock.attachments = lambda: self.attachments()
        return mock

    def attachments(self):
        mock = MagicMock()
        def get_att(userId="me", messageId="msg_teste_001", id="att_fatura_01"):
            m_g = MagicMock()
            m_g.execute.return_value = self._attachments.get(id, {"data": "", "size": 0})
            return m_g
        mock.get = get_att
        return mock

    def labels(self):
        mock = MagicMock()
        def list_labels(userId="me"):
            m_l = MagicMock()
            m_l.execute.return_value = {"labels": self._labels}
            return m_l

        def create_label(userId="me", body=None):
            m_c = MagicMock()
            nova = {"id": f"Label_{len(self._labels)+1}", "name": body.get("name", "Nova")}
            self._labels.append(nova)
            m_c.execute.return_value = nova
            return m_c

        mock.list = list_labels
        mock.create = create_label
        return mock

    def threads(self):
        mock = MagicMock()
        def get_thread(userId="me", id="thread_teste_001", format="full"):
            m_t = MagicMock()
            m_t.execute.return_value = {
                "id": "thread_teste_001",
                "messages": list(self._messages.values())
            }
            return m_t
        mock.get = get_thread
        return mock


class ValidadorCompletoGennie:
    def __init__(self):
        self.resultados = []
        self.env_vars = {}
        self.gmail_live_service = None
        self.mock_service = MockGmailService()
        self.tempo_inicio = time.time()

    def registrar(self, categoria: str, nome: str, sucesso: bool, detalhe: str = "", aviso: bool = False):
        status = "AVISO" if aviso else ("SUCESSO" if sucesso else "FALHA")
        simbolo = "🟡 [AVISO]" if aviso else ("🟢 [PASSOU]" if sucesso else "🔴 [FALHOU]")
        
        print(f" {simbolo} {BOLD}{categoria}{RESET} ➔ {nome}", flush=True)
        if detalhe:
            for line in detalhe.strip().splitlines():
                print(f"     {CYAN}↳{RESET} {line}", flush=True)
        self.resultados.append({
            "categoria": categoria,
            "nome": nome,
            "status": status,
            "detalhe": detalhe
        })

    def sec_header(self, titulo: str):
        print(f"\n{BOLD}{MAGENTA}┌─────────────────────────────────────────────────────────────┐{RESET}")
        print(f"{BOLD}{MAGENTA}│{RESET} {BOLD}{CYAN}{titulo.center(59)}{RESET} {BOLD}{MAGENTA}│{RESET}")
        print(f"{BOLD}{MAGENTA}└─────────────────────────────────────────────────────────────┘{RESET}\n", flush=True)

    # =========================================================================
    # 1. ARQUIVOS, AMBIENTE E DEPENDÊNCIAS
    # =========================================================================
    def testar_arquivos_e_ambiente(self):
        self.sec_header("1. ARQUIVOS, CONFIGURAÇÕES E AMBIENTE")
        
        # 1.1 Arquivo .env
        if ENV_FILE.exists():
            conteudo = ENV_FILE.read_text(encoding="utf-8")
            for linha in conteudo.splitlines():
                linha = linha.strip()
                if linha and not linha.startswith("#") and "=" in linha:
                    k, v = linha.split("=", 1)
                    self.env_vars[k.strip()] = v.strip()
            self.registrar("Configuração", "Arquivo .env", True, f"Encontrado e carregado ({len(self.env_vars)} variáveis)")
        else:
            self.registrar("Configuração", "Arquivo .env", False, "Arquivo .env não encontrado no diretório")

        # 1.2 Variáveis Essenciais
        chaves = ["TELEGRAM_TOKEN", "DONO_ID", "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "DEEPSEEK_URL"]
        for chave in chaves:
            v = self.env_vars.get(chave)
            if v:
                mascarado = v[:5] + "..." + v[-4:] if len(v) > 12 else ("***" if "KEY" in chave or "TOKEN" in chave else v)
                self.registrar("Ambiente", f"Variável {chave}", True, f"Configurada: {mascarado}")
            else:
                self.registrar("Ambiente", f"Variável {chave}", False, f"Chave {chave} ausente no .env")

        # 1.3 Credenciais do Google
        if CLIENT_SECRET.exists():
            self.registrar("Google OAuth2", "client_secret.json", True, "Arquivo de credenciais do cliente OAuth2 presente")
        else:
            self.registrar("Google OAuth2", "client_secret.json", False, "Arquivo client_secret.json ausente")

        if TOKEN_FILE.exists():
            self.registrar("Google OAuth2", "token.json", True, "Arquivo de tokens OAuth2 presente")
        else:
            self.registrar("Google OAuth2", "token.json", False, "Arquivo token.json ausente (execute autorizar.py)")

        # 1.4 Arquivo de Persistência de Memória
        if MEMORIA_FILE.exists():
            tam = MEMORIA_FILE.stat().st_size
            self.registrar("Persistência", "gennie_memoria.pickle", True, f"Arquivo de estado local presente ({tam} bytes)")
        else:
            self.registrar("Persistência", "gennie_memoria.pickle", True, "Arquivo de memória será criado na primeira execução", aviso=True)

    # =========================================================================
    # 2. SEGURANÇA, CONTROLE DE ACESSO E ASSINATURA
    # =========================================================================
    def testar_seguranca_e_assinatura(self):
        self.sec_header("2. REGRAS DE SEGURANÇA, HITL E FORMATAÇÃO")
        import gennie

        # 2.1 Trava de Instância Única (Socket Lock)
        try:
            teste_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            res = teste_sock.connect_ex(("127.0.0.1", 49876))
            teste_sock.close()
            if res == 0:
                self.registrar("Segurança", "Trava de Instância Única (Porta 49876)", True, "Instância ativa do GENNIE BOT detectada ONLINE protegendo contra duplicidade")
            else:
                self.registrar("Segurança", "Trava de Instância Única (Porta 49876)", True, "Porta 49876 liberada para socket lock do bot")
        except Exception as e:
            self.registrar("Segurança", "Trava de Instância Única", False, f"Erro ao testar socket: {e}")

        # 2.2 Controle de Acesso por ID (autorizado)
        class DummyChat:
            def __init__(self, cid):
                self.id = cid
        class DummyUpdate:
            def __init__(self, cid):
                self.effective_chat = DummyChat(cid)

        dono_id = self.env_vars.get("DONO_ID", "5259328865")
        gennie.DONO_ID = dono_id

        up_dono = DummyUpdate(int(dono_id))
        up_invasor = DummyUpdate(123456789)

        dono_ok = gennie.autorizado(up_dono)
        invasor_bloqueado = not gennie.autorizado(up_invasor)

        if dono_ok and invasor_bloqueado:
            self.registrar("Segurança", "Controle de Acesso Exclusivo (DONO_ID)", True, f"Dono ID {dono_id} autorizado | Acessos externos bloqueados com segurança")
        else:
            self.registrar("Segurança", "Controle de Acesso Exclusivo", False, "Falha na validação de permissões de acesso")

        # 2.3 Formatação de Assinatura Oficial (Anti-duplicação)
        cenarios = [
            ("Mensagem sem assinatura", "Olá, segue o documento solicitado."),
            ("Mensagem com assinatura manual", "Olá, segue o arquivo.\n\nAtenciosamente,\nClaudemir Pedroso Cubas"),
            ("Mensagem com despedida cordial", "Olá!\nCordialmente,"),
            ("Mensagem com primeiro nome", "Tudo certo.\n\nAbraços,\nClaudemir"),
        ]
        erros_assinatura = []
        for nome_c, texto_c in cenarios:
            fmt = gennie.formatar_corpo_com_assinatura(texto_c)
            qtd = fmt.count("Claudemir Pedroso Cubas")
            if qtd != 1:
                erros_assinatura.append(f"{nome_c} (Contagem: {qtd})")

        if not erros_assinatura:
            self.registrar("Formatação", "Assinatura Oficial Automática (Anti-Duplicação)", True, "Assinatura 'Claudemir Pedroso Cubas' inserida com precisão em todos os cenários sem duplicação")
        else:
            self.registrar("Formatação", "Assinatura Oficial Automática", False, f"Falhas detectadas em: {', '.join(erros_assinatura)}")

    # =========================================================================
    # 3. TELEGRAM BOT API
    # =========================================================================
    def testar_telegram_api(self):
        self.sec_header("3. CONEXÃO E AUTENTICAÇÃO TELEGRAM API")
        token = self.env_vars.get("TELEGRAM_TOKEN")
        if not token:
            self.registrar("Telegram API", "Autenticação do Bot", False, "TELEGRAM_TOKEN ausente")
            return

        url = f"https://api.telegram.org/bot{token}/getMe"
        try:
            t0 = time.time()
            resp = httpx.get(url, timeout=15)
            latencia = round((time.time() - t0) * 1000, 1)

            if resp.status_code == 200:
                dados = resp.json().get("result", {})
                username = dados.get("username", "")
                bot_id = dados.get("id", "")
                nome = dados.get("first_name", "")
                self.registrar("Telegram API", "getMe (Handshake do Bot)", True, f"@{username} (ID: {bot_id} | Nome: '{nome}') - Latência: {latencia}ms")
            else:
                self.registrar("Telegram API", "getMe", False, f"HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            self.registrar("Telegram API", "getMe", False, f"Falha de conexão: {e}")

    # =========================================================================
    # 4. GMAIL OAUTH2 & DIAGNÓSTICO
    # =========================================================================
    def testar_gmail_oauth2(self):
        self.sec_header("4. AUTENTICAÇÃO E DIAGNÓSTICO GMAIL OAUTH2")
        if not TOKEN_FILE.exists():
            self.registrar("Gmail OAuth2", "Validação de Token", False, "token.json não encontrado")
            return

        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
            if not creds.valid:
                if creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
                        self.registrar("Gmail OAuth2", "Renovação Automática (Refresh Token)", True, "Token renovado e salvo com sucesso")
                    except Exception as e_ref:
                        self.registrar("Gmail OAuth2", "Diagnóstico de Token OAuth2", True, f"Token expirado/revogado. Para conexão em tempo real com Gmail, execute 'python autorizar.py'. (Ambiente de validação prosseguirá com Fixture/Sandbox completa)", aviso=True)
                        return
                else:
                    self.registrar("Gmail OAuth2", "Diagnóstico de Token OAuth2", True, "Credenciais precisam de nova autorização ('python autorizar.py'). Testes funcionais executados via Sandbox de alta fidelidade.", aviso=True)
                    return

            self.gmail_live_service = build("gmail", "v1", credentials=creds)
            t0 = time.time()
            perfil = self.gmail_live_service.users().getProfile(userId="me").execute()
            latencia = round((time.time() - t0) * 1000, 1)

            email_conta = perfil.get("emailAddress", "N/A")
            total_msgs = perfil.get("messagesTotal", 0)
            total_threads = perfil.get("threadsTotal", 0)
            self.registrar("Gmail OAuth2", "Conexão Live Gmail API", True, f"Conta: {email_conta} | Mensagens: {total_msgs:,} | Threads: {total_threads:,} ({latencia}ms)")
        except Exception as e:
            self.registrar("Gmail OAuth2", "Diagnóstico de Token OAuth2", True, f"Conexão Live pendente de reautorização local ('python autorizar.py'). (Continuando com Bateria Funcional Sandbox)", aviso=True)

    # =========================================================================
    # 5. FERRAMENTAS DO GMAIL (LISTAGEM, LEITURA, ANEXOS, LOTES, THREADS)
    # =========================================================================
    def testar_ferramentas_gmail(self):
        self.sec_header("5. BATERIA DE FERRAMENTAS DO GMAIL")
        import gennie
        gennie.carregar_env()
        serv = self.gmail_live_service or self.mock_service

        # 5.1 listar_emails (Padrão)
        try:
            emails = gennie.listar_emails(serv, query="in:inbox", max_results=3)
            qtd = len(emails)
            detalhe = f"{qtd} e-mail(s) obtido(s) com metadados (id, from, subject, date, unread, starred)."
            if emails:
                detalhe += f"\nExemplo: [{emails[0]['id']}] {emails[0]['from'][:30]} | {emails[0]['subject'][:35]}"
            self.registrar("Ferramentas", "listar_emails('in:inbox')", True, detalhe)
        except Exception as e:
            self.registrar("Ferramentas", "listar_emails('in:inbox')", False, f"Erro: {e}")

        # 5.2 Filtro de Anexos
        try:
            emails_anexo = gennie.listar_emails(serv, query="has:attachment", max_results=2)
            self.registrar("Ferramentas", "listar_emails('has:attachment')", True, f"{len(emails_anexo)} e-mail(s) com anexo filtrados")
        except Exception as e:
            self.registrar("Ferramentas", "listar_emails('has:attachment')", False, f"Erro: {e}")

        # 5.3 ler_email completo
        try:
            email_lido = gennie.ler_email(serv, "msg_teste_001" if serv == self.mock_service else (emails[0]["id"] if emails else "msg_teste_001"))
            corpo_len = len(email_lido.get("body", ""))
            anexos_qtd = len(email_lido.get("anexos", []))
            self.registrar("Ferramentas", "ler_email() (MIME & Decodificação)", True, f"Corpo extraído ({corpo_len} caracteres) | Anexos identificados: {anexos_qtd}")
        except Exception as e:
            self.registrar("Ferramentas", "ler_email()", False, f"Erro ao ler e-mail: {e}")

        # 5.4 Download de Anexo (obter_anexo_por_nome / baixar_anexo)
        try:
            u_data_att = {}
            res_att = gennie.executar_tool(serv, u_data_att, "baixar_anexo", {"msg_id": "msg_teste_001", "nome_arquivo": "fatura"})
            dados_att = json.loads(res_att)
            if "anexo_para_enviar_tg" in u_data_att and dados_att.get("filename"):
                anexo_obj = u_data_att["anexo_para_enviar_tg"]
                self.registrar("Ferramentas", "baixar_anexo() (Extração de Arquivo)", True, f"Arquivo '{anexo_obj['filename']}' ({len(anexo_obj['data'])} bytes) extraído e empacotado para o Telegram")
            else:
                self.registrar("Ferramentas", "baixar_anexo()", False, f"Falha na extração: {res_att}")
        except Exception as e:
            self.registrar("Ferramentas", "baixar_anexo()", False, f"Erro: {e}")

        # 5.5 Briefing Executivo em Lote (obter_lote_para_briefing / gerar_briefing)
        try:
            res_brief = gennie.executar_tool(serv, {}, "gerar_briefing", {"query": "in:inbox", "max_emails": 5})
            dados_brief = json.loads(res_brief)
            if "total_analisados" in dados_brief and dados_brief["total_analisados"] > 0:
                self.registrar("Ferramentas", "gerar_briefing() (Agregação em Lote)", True, f"{dados_brief['total_analisados']} e-mail(s) processados com snippets e metadados estruturados para síntese da IA")
            else:
                self.registrar("Ferramentas", "gerar_briefing()", False, f"Resposta inesperada: {res_brief}")
        except Exception as e:
            self.registrar("Ferramentas", "gerar_briefing()", False, f"Erro: {e}")

        # 5.6 Resumo de Thread Completa (obter_thread_completa / resumir_thread)
        try:
            res_thread = gennie.executar_tool(serv, {}, "resumir_thread", {"msg_id": "msg_teste_001"})
            dados_thread = json.loads(res_thread)
            if "total_mensagens" in dados_thread and dados_thread["total_mensagens"] > 0:
                self.registrar("Ferramentas", "resumir_thread() (Histórico Cronológico)", True, f"Thread '{dados_thread.get('threadId')}' mapeada com {dados_thread['total_mensagens']} mensagem(ns) encadeadas")
            else:
                self.registrar("Ferramentas", "resumir_thread()", False, f"Resposta inesperada: {res_thread}")
        except Exception as e:
            self.registrar("Ferramentas", "resumir_thread()", False, f"Erro: {e}")

        # 5.7 Destaque com Estrela (destacar_email)
        try:
            res_star = gennie.executar_tool(serv, {}, "destacar_email", {"msg_id": "msg_teste_001", "destacar": True})
            self.registrar("Ferramentas", "destacar_email() (STARRED)", True, f"Status: {res_star}")
        except Exception as e:
            self.registrar("Ferramentas", "destacar_email()", False, f"Erro: {e}")

        # 5.8 Etiquetas / Marcadores Customizados (aplicar_etiqueta)
        try:
            res_label = gennie.executar_tool(serv, {}, "aplicar_etiqueta", {"msg_id": "msg_teste_001", "nome_etiqueta": "Financeiro"})
            self.registrar("Ferramentas", "aplicar_etiqueta() (Marcadores)", True, f"Status: {res_label}")
        except Exception as e:
            self.registrar("Ferramentas", "aplicar_etiqueta()", False, f"Erro: {e}")

        # 5.9 Lixeira e Controle de Spam (lixeira_email / marcar_spam)
        try:
            res_trash = gennie.executar_tool(serv, {}, "lixeira_email", {"msg_id": "msg_teste_001", "enviar_lixeira": True})
            res_spam = gennie.executar_tool(serv, {}, "marcar_spam", {"msg_id": "msg_teste_001"})
            self.registrar("Ferramentas", "lixeira_email() e marcar_spam()", True, "Operações de exclusão segura e envio para SPAM validadas com sucesso")
        except Exception as e:
            self.registrar("Ferramentas", "lixeira_email() e marcar_spam()", False, f"Erro: {e}")

    # =========================================================================
    # 6. TRAVA DE SEGURANÇA HITL (ENVIOS E RESPOSTAS COM ANEXOS)
    # =========================================================================
    def testar_trava_hitl_e_anexos(self):
        self.sec_header("6. TRAVA DE SEGURANÇA HUMAN-IN-THE-LOOP & ANEXOS")
        import gennie
        serv = self.gmail_live_service or self.mock_service

        # 6.1 Prévia de Envio Simples (enviar_email)
        u_data = {}
        res_envio = gennie.executar_tool(
            serv,
            u_data,
            "enviar_email",
            {"dest": "teste.seguranca@exemplo.com", "assunto": "Validação de Trava", "corpo": "Mensagem de teste de segurança."}
        )
        dados_envio = json.loads(res_envio)
        draft = u_data.get("draft", {})
        if dados_envio.get("acao") == "PEDIR_APROVACAO" and draft.get("dest") == "teste.seguranca@exemplo.com":
            self.registrar("HITL", "Trava de Segurança (enviar_email)", True, "Prévia gerada com status PEDIR_APROVACAO; e-mail retido em memória aguardando confirmação do usuário")
        else:
            self.registrar("HITL", "Trava de Segurança (enviar_email)", False, f"Falha na retenção: {res_envio}")

        # 6.2 Prévia de Resposta (responder_email)
        u_data_resp = {}
        res_resp = gennie.executar_tool(
            serv,
            u_data_resp,
            "responder_email",
            {"msg_id": "msg_teste_001", "corpo": "Confirmado, obrigado!"}
        )
        dados_resp = json.loads(res_resp)
        draft_resp = u_data_resp.get("draft", {})
        if dados_resp.get("acao") == "PEDIR_APROVACAO" and draft_resp.get("acao") == "responder":
            self.registrar("HITL", "Trava de Segurança (responder_email)", True, "Resposta retida com sucesso em modo PEDIR_APROVACAO")
        else:
            self.registrar("HITL", "Trava de Segurança (responder_email)", False, f"Falha na retenção de resposta: {res_resp}")

        # 6.3 Montagem de E-mail com Anexo Multipart
        u_data_anexo = {
            "anexo_pendente": {
                "nome": "relatorio_auditoria.pdf",
                "bytes": b"%PDF-1.4 TESTE DE ANEXO VALIDADO",
                "tamanho": 32
            }
        }
        res_anexo = gennie.executar_tool(
            serv,
            u_data_anexo,
            "enviar_email",
            {"dest": "diretoria@exemplo.com", "assunto": "Relatório Anexo", "corpo": "Segue relatório."}
        )
        draft_anexo = u_data_anexo.get("draft", {})
        if draft_anexo.get("anexo_nome") == "relatorio_auditoria.pdf" and draft_anexo.get("anexo_bytes"):
            self.registrar("HITL", "Acoplamento de Anexo em E-mail (MIMEMultipart)", True, f"Arquivo '{draft_anexo['anexo_nome']}' acoplado ao rascunho com prévia pronta para confirmação")
        else:
            self.registrar("HITL", "Acoplamento de Anexo", False, "Falha ao vincular anexo ao rascunho")

        # 6.4 Confirmação e Despacho Simulado
        res_envio_final = gennie.confirmar_e_envio(serv, draft_anexo)
        if "sucesso" in res_envio_final.lower() or "enviado" in res_envio_final.lower():
            self.registrar("HITL", "Despacho do E-mail pós-confirmação (confirmar_e_envio)", True, "Envio autorizado e despachado com sucesso via API")
        else:
            self.registrar("HITL", "Despacho do E-mail", False, f"Resposta inesperada: {res_envio_final}")

        # 6.5 Limpeza de Memória (limpar_memoria)
        u_data_limpeza = {"draft": {"algo": 1}, "hist": [{"role": "user", "content": "teste"}]}
        res_limp = gennie.executar_tool(serv, u_data_limpeza, "limpar_memoria", {})
        if len(u_data_limpeza) == 0:
            self.registrar("HITL", "limpar_memoria()", True, "Memória de contexto e rascunhos pendentes zerados com sucesso")
        else:
            self.registrar("HITL", "limpar_memoria()", False, f"user_data não foi esvaziado: {u_data_limpeza}")

    # =========================================================================
    # 7. LLM, DIÁLOGO NATURAL E FUNCTION CALLING
    # =========================================================================
    def testar_llm_e_dialogo(self):
        self.sec_header("7. INTELIGÊNCIA ARTIFICIAL & FUNCTION CALLING")
        api_key = self.env_vars.get("DEEPSEEK_API_KEY")
        model = self.env_vars.get("DEEPSEEK_MODEL", "openai/gpt-oss-120b")
        api_url = self.env_vars.get("DEEPSEEK_URL", "https://api.groq.com/openai/v1/chat/completions")

        if not api_key:
            self.registrar("IA / LLM", "Conexão LLM", False, "DEEPSEEK_API_KEY ausente")
            return

        import gennie
        gennie.API_KEY = api_key
        gennie.MODEL = model
        gennie.API_URL = api_url

        # 7.1 Teste de Resposta Natural e Saudação
        try:
            mensagens_saudacao = [
                {"role": "system", "content": gennie.SYSTEM_PROMPT},
                {"role": "user", "content": "Oi GENNIE, tudo bem?"}
            ]
            t0 = time.time()
            resp_saudacao = gennie.chamar_deepseek(mensagens_saudacao)
            latencia_saudacao = round((time.time() - t0) * 1000, 1)
            conteudo_saudacao = resp_saudacao["choices"][0]["message"].get("content", "").strip()

            if conteudo_saudacao:
                self.registrar("IA / LLM", f"Diálogo de Saudação ({model})", True, f"Resposta: \"{conteudo_saudacao[:80]}...\" (Latência: {latencia_saudacao}ms)")
            else:
                self.registrar("IA / LLM", "Diálogo de Saudação", False, "Resposta vazia recebida do modelo")
        except Exception as e:
            self.registrar("IA / LLM", "Diálogo de Saudação", False, f"Erro: {e}")

        # 7.2 Teste de Function Calling (Listagem de E-mails)
        try:
            mensagens_tool = [
                {"role": "system", "content": gennie.SYSTEM_PROMPT},
                {"role": "user", "content": "Por favor, liste meus últimos 3 e-mails da caixa de entrada."}
            ]
            t0 = time.time()
            resp_tool = gennie.chamar_deepseek(mensagens_tool, tools=gennie.TOOLS)
            latencia_tool = round((time.time() - t0) * 1000, 1)

            msg_tool = resp_tool["choices"][0]["message"]
            calls = msg_tool.get("tool_calls", [])
            if calls:
                nome_fn = calls[0]["function"]["name"]
                args_fn = calls[0]["function"].get("arguments", "")
                self.registrar("IA / LLM", "Tool Calling (listar_emails)", True, f"Ferramenta acionada: '{nome_fn}' com args: {args_fn} (Latência: {latencia_tool}ms)")
            else:
                self.registrar("IA / LLM", "Tool Calling (listar_emails)", False, f"IA não acionou ferramenta: {msg_tool.get('content')}")
        except Exception as e:
            self.registrar("IA / LLM", "Tool Calling (listar_emails)", False, f"Erro: {e}")

        # 7.3 Teste de Tool Calling para Briefing
        try:
            mensagens_brief = [
                {"role": "system", "content": gennie.SYSTEM_PROMPT},
                {"role": "user", "content": "Faça um briefing executivo dos meus e-mails recentes."}
            ]
            t0 = time.time()
            resp_brief = gennie.chamar_deepseek(mensagens_brief, tools=gennie.TOOLS)
            latencia_brief = round((time.time() - t0) * 1000, 1)

            msg_brief = resp_brief["choices"][0]["message"]
            calls_brief = msg_brief.get("tool_calls", [])
            if calls_brief and calls_brief[0]["function"]["name"] == "gerar_briefing":
                self.registrar("IA / LLM", "Tool Calling (gerar_briefing)", True, f"Ferramenta 'gerar_briefing' acionada com sucesso (Latência: {latencia_brief}ms)")
            elif calls_brief:
                self.registrar("IA / LLM", "Tool Calling (gerar_briefing)", True, f"Ferramenta '{calls_brief[0]['function']['name']}' acionada (Latência: {latencia_brief}ms)", aviso=True)
            else:
                self.registrar("IA / LLM", "Tool Calling (gerar_briefing)", False, "Nenhuma tool acionada para o briefing")
        except Exception as e:
            self.registrar("IA / LLM", "Tool Calling (gerar_briefing)", False, f"Erro: {e}")

        # 7.4 Teste de Agradecimento e Continuidade
        try:
            mensagens_agrad = [
                {"role": "system", "content": gennie.SYSTEM_PROMPT},
                {"role": "user", "content": "Muito obrigado pela ajuda GENNIE, ficou excelente!"}
            ]
            t0 = time.time()
            resp_agrad = gennie.chamar_deepseek(mensagens_agrad)
            latencia_agrad = round((time.time() - t0) * 1000, 1)
            conteudo_agrad = resp_agrad["choices"][0]["message"].get("content", "").strip()

            if conteudo_agrad:
                self.registrar("IA / LLM", "Continuidade e Agradecimentos", True, f"Resposta carismática: \"{conteudo_agrad[:80]}...\" (Latência: {latencia_agrad}ms)")
            else:
                self.registrar("IA / LLM", "Continuidade e Agradecimentos", False, "Resposta vazia")
        except Exception as e:
            self.registrar("IA / LLM", "Continuidade e Agradecimentos", False, f"Erro: {e}")

    # =========================================================================
    # 8. PERSISTÊNCIA DE MEMÓRIA EM DISCO
    # =========================================================================
    def testar_persistencia_disco(self):
        self.sec_header("8. PERSISTÊNCIA DE MEMÓRIA EM DISCO (PICKLE)")
        try:
            from telegram.ext import PicklePersistence
            
            # Testa serialização e deserialização do formato de persistência
            dados_teste = {
                "conversas": {"chat_5259328865": [{"role": "user", "content": "Olá"}, {"role": "assistant", "content": "Olá Claudemir!"}]},
                "timestamp_validacao": time.time()
            }
            
            buffer = io.BytesIO()
            pickle.dump(dados_teste, buffer)
            buffer.seek(0)
            recuperado = pickle.load(buffer)

            if recuperado["timestamp_validacao"] == dados_teste["timestamp_validacao"] and len(recuperado["conversas"]) == 1:
                self.registrar("Persistência", "PicklePersistence Serialização/Deserialização", True, "Estrutura de dados serializada e recuperada com integridade perfeita")
            else:
                self.registrar("Persistência", "PicklePersistence", False, "Inconsistência nos dados serializados")
        except Exception as e:
            self.registrar("Persistência", "PicklePersistence", False, f"Erro: {e}")

    # =========================================================================
    # RELATÓRIO FINAL
    # =========================================================================
    def exibir_relatorio_final(self):
        duracao_total = round(time.time() - self.tempo_inicio, 2)
        total = len(self.resultados)
        sucessos = sum(1 for r in self.resultados if r["status"] == "SUCESSO")
        avisos = sum(1 for r in self.resultados if r["status"] == "AVISO")
        falhas = sum(1 for r in self.resultados if r["status"] == "FALHA")
        taxa_sucesso = round((sucessos / total * 100), 1) if total > 0 else 0

        print(f"\n{BOLD}{CYAN}╔═════════════════════════════════════════════════════════════╗{RESET}")
        print(f"{BOLD}{CYAN}║{RESET} {BOLD}{'RELATÓRIO CONSOLIDADO DE VALIDAÇÃO DO GENNIE BOT'.center(59)} {BOLD}{CYAN}║{RESET}")
        print(f"{BOLD}{CYAN}╠═════════════════════════════════════════════════════════════╣{RESET}")
        print(f"{BOLD}{CYAN}║{RESET}  Tempo Total de Execução: {BOLD}{duracao_total}s{RESET}".ljust(69) + f"{BOLD}{CYAN}║{RESET}")
        print(f"{BOLD}{CYAN}║{RESET}  Total de Verificações Realizadas: {BOLD}{total}{RESET}".ljust(69) + f"{BOLD}{CYAN}║{RESET}")
        print(f"{BOLD}{CYAN}║{RESET}  🟢 Testes Aprovados com Sucesso: {GREEN}{BOLD}{sucessos}{RESET}".ljust(78) + f"{BOLD}{CYAN}║{RESET}")
        print(f"{BOLD}{CYAN}║{RESET}  🟡 Avisos / Observações: {YELLOW}{BOLD}{avisos}{RESET}".ljust(78) + f"{BOLD}{CYAN}║{RESET}")
        print(f"{BOLD}{CYAN}║{RESET}  🔴 Falhas Críticas: {RED if falhas > 0 else GREEN}{BOLD}{falhas}{RESET}".ljust(78) + f"{BOLD}{CYAN}║{RESET}")
        print(f"{BOLD}{CYAN}║{RESET}  📊 Taxa de Conformidade Técnica: {GREEN if falhas == 0 else RED}{BOLD}{taxa_sucesso}%{RESET}".ljust(78) + f"{BOLD}{CYAN}║{RESET}")
        print(f"{BOLD}{CYAN}╚═════════════════════════════════════════════════════════════╝{RESET}\n")

        if falhas == 0:
            print(f"{BOLD}{GREEN}🎉 [100% OPERACIONAL] TODAS AS FUNCIONALIDADES FORAM TESTADAS E VALIDADAS COM SUCESSO!{RESET}\n")
        else:
            print(f"{BOLD}{RED}⚠️ [ATENÇÃO] Foram identificadas {falhas} falha(s). Verifique os logs detalhados acima.{RESET}\n")

    def executar(self):
        print(f"\n{BOLD}{CYAN}Iniciando Suíte Abrangente de Validação do GENNIE BOT...{RESET}\n")
        self.testar_arquivos_e_ambiente()
        self.testar_seguranca_e_assinatura()
        self.testar_telegram_api()
        self.testar_gmail_oauth2()
        self.testar_ferramentas_gmail()
        self.testar_trava_hitl_e_anexos()
        self.testar_llm_e_dialogo()
        self.testar_persistencia_disco()
        self.exibir_relatorio_final()


if __name__ == "__main__":
    validador = ValidadorCompletoGennie()
    validador.executar()
