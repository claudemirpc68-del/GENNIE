"""
Script de Teste e Validação do GENNIE_BOT
Valida dependências, variáveis de ambiente, Telegram API, Gmail OAuth2, LLM e Function Calling.
"""

import io
import json
import os
import sys
import time
from pathlib import Path
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
BOLD = "\033[1m"
RESET = "\033[0m"

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
TOKEN_FILE = BASE_DIR / "token.json"
CLIENT_SECRET = BASE_DIR / "client_secret.json"

class ValidadorBot:
    def __init__(self):
        self.resultados = []
        self.env_vars = {}
        self.gmail_service = None

    def log_resultado(self, categoria: str, nome: str, sucesso: bool, detalhe: str = "", aviso: bool = False):
        status = "AVISO" if aviso else ("SUCESSO" if sucesso else "FALHA")
        cor = YELLOW if aviso else (GREEN if sucesso else RED)
        simbolo = "[!]" if aviso else ("[OK]" if sucesso else "[X]")
        
        print(f" {simbolo} [{cor}{status}{RESET}] {BOLD}{categoria}{RESET} -> {nome}")
        if detalhe:
            for line in detalhe.strip().splitlines():
                print(f"     {CYAN}->{RESET} {line}")
        self.resultados.append({"categoria": categoria, "nome": nome, "status": status, "detalhe": detalhe})

    def validar_arquivos_e_env(self):
        print(f"\n{BOLD}{CYAN}=== 1. Verificação de Arquivos e Variáveis de Ambiente ==={RESET}")
        
        # 1.1 Arquivo .env
        if not ENV_FILE.exists():
            self.log_resultado("Arquivos", "Arquivo .env", False, f"Não encontrado em: {ENV_FILE}")
            return
        
        conteudo_env = ENV_FILE.read_text(encoding="utf-8")
        for linha in conteudo_env.splitlines():
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                k, v = linha.split("=", 1)
                self.env_vars[k.strip()] = v.strip()

        self.log_resultado("Arquivos", "Arquivo .env", True, f"Encontrado ({len(self.env_vars)} chaves carregadas)")

        # 1.2 Variáveis obrigatórias
        chaves_esperadas = ["TELEGRAM_TOKEN", "DONO_ID", "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "DEEPSEEK_URL"]
        for chave in chaves_esperadas:
            val = self.env_vars.get(chave)
            if val:
                val_mascarado = val[:6] + "..." + val[-4:] if len(val) > 10 else "***"
                self.log_resultado("Variáveis", chave, True, f"Definida ({val_mascarado})")
            else:
                self.log_resultado("Variáveis", chave, False, "Chave vazia ou ausente no .env")

        # 1.3 Credenciais do Google
        if CLIENT_SECRET.exists():
            self.log_resultado("Arquivos", "client_secret.json", True, "Arquivo de credenciais OAuth2 presente")
        else:
            self.log_resultado("Arquivos", "client_secret.json", False, "Arquivo client_secret.json ausente")

        if TOKEN_FILE.exists():
            self.log_resultado("Arquivos", "token.json", True, "Token de autorização do Gmail presente")
        else:
            self.log_resultado("Arquivos", "token.json", False, "Arquivo token.json ausente. Execute autorizar.py primeiro")

    def validar_telegram_api(self):
        print(f"\n{BOLD}{CYAN}=== 2. Validação da API do Telegram ==={RESET}")
        token = self.env_vars.get("TELEGRAM_TOKEN")
        if not token:
            self.log_resultado("Telegram", "Conexão Bot", False, "TELEGRAM_TOKEN ausente")
            return

        url = f"https://api.telegram.org/bot{token}/getMe"
        try:
            inicio = time.time()
            resp = httpx.get(url, timeout=15)
            duracao = round((time.time() - inicio) * 1000, 2)

            if resp.status_code == 200:
                dados = resp.json().get("result", {})
                bot_username = dados.get("username", "Desconhecido")
                bot_id = dados.get("id", "Desconhecido")
                bot_nome = dados.get("first_name", "")
                self.log_resultado(
                    "Telegram", 
                    "getMe (Autenticação)", 
                    True, 
                    f"Bot: @{bot_username} (ID: {bot_id} | Nome: '{bot_nome}') - Latência: {duracao}ms"
                )
            else:
                self.log_resultado("Telegram", "getMe (Autenticação)", False, f"HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            self.log_resultado("Telegram", "getMe (Autenticação)", False, f"Exceção: {type(e).__name__} - {e}")

    def validar_gmail_api(self):
        print(f"\n{BOLD}{CYAN}=== 3. Validação do Gmail OAuth2 & Conexão ==={RESET}")
        if not TOKEN_FILE.exists():
            self.log_resultado("Gmail", "Serviço Gmail", False, "token.json não existe para iniciar validação")
            return

        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
            if not creds.valid:
                if creds.expired and creds.refresh_token:
                    print(f"     {YELLOW}[i] Atualizando credenciais expiradas via refresh_token...{RESET}")
                    creds.refresh(Request())
                    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
                    self.log_resultado("Gmail", "OAuth2 Refresh", True, "Token renovado e salvo com sucesso")
                else:
                    self.log_resultado("Gmail", "OAuth2 Validade", False, "Credenciais inválidas e sem refresh token")
                    return

            self.gmail_service = build("gmail", "v1", credentials=creds)
            
            # Teste de leitura de perfil
            perfil = self.gmail_service.users().getProfile(userId="me").execute()
            email_addr = perfil.get("emailAddress", "N/A")
            total_msgs = perfil.get("messagesTotal", 0)
            total_threads = perfil.get("threadsTotal", 0)

            self.log_resultado(
                "Gmail",
                "Perfil do Usuário (getProfile)",
                True,
                f"Conta: {email_addr} | Total de Mensagens: {total_msgs} | Threads: {total_threads}"
            )
        except Exception as e:
            self.log_resultado("Gmail", "Serviço Gmail", False, f"Erro ao inicializar API: {e}")

    def validar_ferramentas_locais(self):
        print(f"\n{BOLD}{CYAN}=== 4. Validação das Ferramentas do GENNIE ==={RESET}")
        if not self.gmail_service:
            self.log_resultado("Ferramentas", "Execução de Tools", False, "Gmail API não conectada")
            return

        try:
            # Importa as funções direto do gennie.py
            import gennie

            # 4.1 Teste de Listar Emails
            emails = gennie.listar_emails(self.gmail_service, query="in:inbox", max_results=3)
            qtd = len(emails)
            detalhe_emails = f"{qtd} e-mail(s) obtido(s) na Inbox."
            if emails:
                primeiro = emails[0]
                detalhe_emails += f"\nÚltimo: [ID: {primeiro['id']}] De: {primeiro['from'][:30]} | Assunto: {primeiro['subject'][:40]}"
            self.log_resultado("Ferramentas", "listar_emails()", True, detalhe_emails)

            # 4.2 Teste de Leitura de E-mail
            if emails:
                primeiro_id = emails[0]["id"]
                email_lido = gennie.ler_email(self.gmail_service, primeiro_id)
                if email_lido and "body" in email_lido:
                    tam_corpo = len(email_lido.get("body", ""))
                    self.log_resultado("Ferramentas", "ler_email()", True, f"E-mail {primeiro_id} lido com sucesso ({tam_corpo} caracteres no corpo)")
                else:
                    self.log_resultado("Ferramentas", "ler_email()", False, "Estrutura do e-mail lido inválida")
            else:
                self.log_resultado("Ferramentas", "ler_email()", True, "Nenhum e-mail na inbox para teste de leitura", aviso=True)

            # 4.3 Teste de Trava de Segurança em Prévia de Envio
            user_data_simulado = {}
            res_draft = gennie.executar_tool(
                self.gmail_service, 
                user_data_simulado, 
                "enviar_email", 
                {"dest": "teste@exemplo.com", "assunto": "Teste de Validação", "corpo": "Olá, este é um teste."}
            )
            dados_draft = json.loads(res_draft)
            if dados_draft.get("acao") == "PEDIR_APROVACAO" and "draft" in user_data_simulado:
                self.log_resultado("Ferramentas", "Trava de Segurança (enviar_email)", True, "Prévia gerada com status PEDIR_APROVACAO sem envio imediato")
            else:
                self.log_resultado("Ferramentas", "Trava de Segurança (enviar_email)", False, f"Resposta inesperada: {res_draft}")

        except Exception as e:
            self.log_resultado("Ferramentas", "Execução de Tools", False, f"Erro ao testar ferramentas: {e}")

    def validar_llm_e_function_calling(self):
        print(f"\n{BOLD}{CYAN}=== 5. Validação do Modelo de IA & Function Calling ==={RESET}")
        api_key = self.env_vars.get("DEEPSEEK_API_KEY")
        model = self.env_vars.get("DEEPSEEK_MODEL", "llama-3.3-70b-versatile")
        api_url = self.env_vars.get("DEEPSEEK_URL", "https://api.groq.com/openai/v1/chat/completions")

        if not api_key:
            self.log_resultado("LLM", "Conexão LLM", False, "DEEPSEEK_API_KEY ausente")
            return

        try:
            import gennie
            gennie.API_KEY = api_key
            gennie.MODEL = model
            gennie.API_URL = api_url

            # 5.1 Teste de Resposta Simples
            mensagens_teste = [
                {"role": "system", "content": "Você é um assistente de teste. Responda apenas com 'OK'."},
                {"role": "user", "content": "Status?"}
            ]
            
            inicio = time.time()
            resp = gennie.chamar_deepseek(mensagens_teste)
            duracao = round((time.time() - inicio) * 1000, 2)
            
            conteudo = resp["choices"][0]["message"].get("content", "").strip()
            self.log_resultado("LLM", f"Resposta Básica ({model})", True, f"Resposta: '{conteudo}' - Latência: {duracao}ms")

            # 5.2 Teste de Function Calling (Tool Use)
            mensagens_tool = [
                {"role": "system", "content": gennie.SYSTEM_PROMPT},
                {"role": "user", "content": "Por favor, liste os meus 3 últimos e-mails não lidos."}
            ]
            inicio = time.time()
            resp_tool = gennie.chamar_deepseek(mensagens_tool, tools=gennie.TOOLS)
            duracao_tool = round((time.time() - inicio) * 1000, 2)

            msg_tool = resp_tool["choices"][0]["message"]
            chamadas = msg_tool.get("tool_calls", [])
            if chamadas:
                tool_chamada = chamadas[0]["function"]["name"]
                args_chamada = chamadas[0]["function"].get("arguments", "")
                self.log_resultado(
                    "LLM",
                    "Function Calling (Tool Use)",
                    True,
                    f"A IA acionou a ferramenta '{tool_chamada}' com argumentos: {args_chamada} (Latência: {duracao_tool}ms)"
                )
            else:
                self.log_resultado(
                    "LLM",
                    "Function Calling (Tool Use)",
                    False,
                    f"A IA não chamou nenhuma ferramenta. Resposta recebida: {msg_tool.get('content')}"
                )

        except Exception as e:
            self.log_resultado("LLM", "Conexão e Inferência", False, f"Erro: {type(e).__name__} - {e}")

    def exibir_resumo(self):
        print(f"\n{BOLD}{CYAN}================== RESUMO DA VALIDAÇÃO =================={RESET}")
        total = len(self.resultados)
        sucessos = sum(1 for r in self.resultados if r["status"] == "SUCESSO")
        falhas = sum(1 for r in self.resultados if r["status"] == "FALHA")
        avisos = sum(1 for r in self.resultados if r["status"] == "AVISO")

        print(f" Total de Verificações: {BOLD}{total}{RESET}")
        print(f" [OK] {GREEN}Sucessos:{RESET} {BOLD}{sucessos}{RESET}")
        print(f" [!]  {YELLOW}Avisos:{RESET}   {BOLD}{avisos}{RESET}")
        print(f" [X]  {RED}Falhas:{RESET}   {BOLD}{falhas}{RESET}")

        if falhas == 0:
            print(f"\n{BOLD}{GREEN}>>> TODAS AS VALIDAÇÕES PASSARAM COM SUCESSO! O BOT ESTÁ 100% OPERACIONAL. <<<{RESET}\n")
        else:
            print(f"\n{BOLD}{RED}>>> ATENÇÃO: Foram identificadas {falhas} falha(s). Verifique os detalhes acima. <<<{RESET}\n")

    def executar(self):
        print(f"{BOLD}{CYAN}Iniciando bateria de testes do GENNIE_BOT...{RESET}")
        self.validar_arquivos_e_env()
        self.validar_telegram_api()
        self.validar_gmail_api()
        self.validar_ferramentas_locais()
        self.validar_llm_e_function_calling()
        self.exibir_resumo()

if __name__ == "__main__":
    validador = ValidadorBot()
    validador.executar()
