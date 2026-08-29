"""
====================================================================
GENNIE BOT - Script de Validação da Ponte REST com o BOT ALFREDO
====================================================================
Testa de ponta a ponta:
 1. Inicialização do Bridge Server (aiohttp.web)
 2. Health check e rotas públicas
 3. Middleware de Segurança (Bloqueio 401 para requisições não autorizadas)
 4. Endpoints REST protegidos (/recentes, /briefing, /ler, /preparar)
 5. Cliente GennieService do repositório do ALFREDO comunicando-se com a GENNIE
 6. Tool 'enviar_para_alfredo' no motor de Function Calling da GENNIE
====================================================================
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
import httpx
from aiohttp import web

# Garante suporte UTF-8 no terminal Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Adiciona o pacote do Alfredo ao path temporariamente para testar o GennieService
ALFREDO_PKG_DIR = BASE_DIR / "alfredo_package"
if str(ALFREDO_PKG_DIR) not in sys.path:
    sys.path.insert(0, str(ALFREDO_PKG_DIR))

import bridge_server
import gennie
from bot.services.gennie_service import GennieService

# Cores ANSI
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

TEST_PORT = 8990
TEST_SECRET = "token_teste_ponte_alfredo_gennie_2026"


class ValidadorPonte:
    def __init__(self):
        self.resultados = []
        self.runner = None
        self.base_url = f"http://127.0.0.1:{TEST_PORT}"
        self.tempo_inicio = time.time()

    def registrar(self, categoria: str, nome: str, sucesso: bool, detalhe: str = ""):
        status = "SUCESSO" if sucesso else "FALHA"
        simbolo = "🟢 [PASSOU]" if sucesso else "🔴 [FALHOU]"
        print(f" {simbolo} {BOLD}{categoria}{RESET} ➔ {nome}", flush=True)
        if detalhe:
            for line in detalhe.strip().splitlines():
                print(f"     {CYAN}↳{RESET} {line}", flush=True)
        self.resultados.append({"categoria": categoria, "nome": nome, "status": status, "detalhe": detalhe})

    def sec_header(self, titulo: str):
        print(f"\n{BOLD}{MAGENTA}┌─────────────────────────────────────────────────────────────┐{RESET}")
        print(f"{BOLD}{MAGENTA}│{RESET} {BOLD}{CYAN}{titulo.center(59)}{RESET} {BOLD}{MAGENTA}│{RESET}")
        print(f"{BOLD}{MAGENTA}└─────────────────────────────────────────────────────────────┘{RESET}\n", flush=True)

    async def iniciar_servidor_teste(self):
        self.sec_header("1. INICIALIZAÇÃO DO SERVIDOR DE PONTE (BRIDGE)")
        bridge_server.BRIDGE_SECRET_KEY = TEST_SECRET
        bridge_server.BRIDGE_PORT = TEST_PORT
        bridge_server.BRIDGE_HOST = "127.0.0.1"

        # Configura Mock de serviço para teste funcional determinístico
        from validar_funcionalidades import MockGmailService
        gennie._mock_service_override = MockGmailService()

        try:
            app = bridge_server.criar_app_bridge()
            self.runner = web.AppRunner(app)
            await self.runner.setup()
            site = web.TCPSite(self.runner, "127.0.0.1", TEST_PORT)
            await site.start()
            self.registrar("Bridge Server", "Inicialização TCP (Porta 8990)", True, f"Servidor REST aiohttp ativo em {self.base_url}")
        except Exception as e:
            self.registrar("Bridge Server", "Inicialização", False, f"Erro ao subir servidor: {e}")

    async def testar_seguranca_e_autenticacao(self):
        self.sec_header("2. VALIDAÇÃO DE SEGURANÇA E AUTENTICAÇÃO (BEARER)")
        async with httpx.AsyncClient(timeout=5) as client:
            # 2.1 Rota pública /health
            try:
                r_health = await client.get(f"{self.base_url}/health")
                if r_health.status_code == 200 and r_health.json().get("status") == "online":
                    self.registrar("Segurança", "Rota Pública /health", True, "Acesso livre sem necessidade de token autenticado")
                else:
                    self.registrar("Segurança", "Rota Pública /health", False, f"Resposta inesperada: {r_health.text}")
            except Exception as e:
                self.registrar("Segurança", "Rota Pública /health", False, f"Erro: {e}")

            # 2.2 Bloqueio de rota protegida sem cabeçalho Authorization
            try:
                r_no_auth = await client.get(f"{self.base_url}/api/v1/emails/recentes")
                if r_no_auth.status_code == 401:
                    self.registrar("Segurança", "Bloqueio de Acesso sem Token (HTTP 401)", True, "Requisição sem Authorization bloqueada com sucesso")
                else:
                    self.registrar("Segurança", "Bloqueio sem Token", False, f"Esperava 401, obteve: {r_no_auth.status_code}")
            except Exception as e:
                self.registrar("Segurança", "Bloqueio sem Token", False, f"Erro: {e}")

            # 2.3 Bloqueio com Token Incorreto
            try:
                r_bad_auth = await client.get(
                    f"{self.base_url}/api/v1/emails/recentes",
                    headers={"Authorization": "Bearer token_falso_123"}
                )
                if r_bad_auth.status_code == 401:
                    self.registrar("Segurança", "Bloqueio de Token Inválido (HTTP 401)", True, "Token incorreto rejeitado pelo middleware de autenticação")
                else:
                    self.registrar("Segurança", "Bloqueio com Token Inválido", False, f"Esperava 401, obteve: {r_bad_auth.status_code}")
            except Exception as e:
                self.registrar("Segurança", "Bloqueio com Token Inválido", False, f"Erro: {e}")

    async def testar_endpoints_rest(self):
        self.sec_header("3. TESTES DOS ENDPOINTS DA PONTE REST")
        headers = {"Authorization": f"Bearer {TEST_SECRET}", "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=10) as client:
            # 3.1 Status da Ponte e Gmail
            try:
                r_st = await client.get(f"{self.base_url}/api/v1/status", headers=headers)
                if r_st.status_code == 200:
                    dados_st = r_st.json()
                    self.registrar("Endpoints", "GET /api/v1/status", True, f"Bot: {dados_st.get('bot')} | Modelo: {dados_st.get('llm_model')}")
                else:
                    self.registrar("Endpoints", "GET /api/v1/status", False, f"Erro: {r_st.text}")
            except Exception as e:
                self.registrar("Endpoints", "GET /api/v1/status", False, f"Erro: {e}")

            # 3.2 Listagem de E-mails Recentes
            try:
                r_rec = await client.get(f"{self.base_url}/api/v1/emails/recentes?max_results=3", headers=headers)
                if r_rec.status_code == 200 and "emails" in r_rec.json():
                    dados_rec = r_rec.json()
                    self.registrar("Endpoints", "GET /api/v1/emails/recentes", True, f"Retornados {dados_rec.get('total')} e-mails estruturados em JSON")
                else:
                    self.registrar("Endpoints", "GET /api/v1/emails/recentes", False, f"Erro: {r_rec.text}")
            except Exception as e:
                self.registrar("Endpoints", "GET /api/v1/emails/recentes", False, f"Erro: {e}")

            # 3.3 Briefing em Lote para o /boletim
            try:
                r_brief = await client.get(f"{self.base_url}/api/v1/emails/briefing?max_emails=4&sintetizar=false", headers=headers)
                if r_brief.status_code == 200 and "total_analisados" in r_brief.json():
                    dados_br = r_brief.json()
                    self.registrar("Endpoints", "GET /api/v1/emails/briefing", True, f"{dados_br.get('total_analisados')} e-mails agregados para o boletim do Alfredo")
                else:
                    self.registrar("Endpoints", "GET /api/v1/emails/briefing", False, f"Erro: {r_brief.text}")
            except Exception as e:
                self.registrar("Endpoints", "GET /api/v1/emails/briefing", False, f"Erro: {e}")

            # 3.4 Preparação de Rascunho com Trava HITL
            try:
                corpo_teste = "Prezado cliente, segue a confirmação do agendamento."
                payload_draft = {
                    "dest": "cliente@exemplo.com",
                    "assunto": "Confirmação de Reunião",
                    "corpo": corpo_teste
                }
                r_draft = await client.post(f"{self.base_url}/api/v1/emails/preparar", json=payload_draft, headers=headers)
                if r_draft.status_code == 200:
                    dados_dr = r_draft.json()
                    if dados_dr.get("acao") == "PEDIR_APROVACAO" and "Claudemir Pedroso Cubas" in dados_dr.get("draft", {}).get("corpo", ""):
                        self.registrar("Endpoints", "POST /api/v1/emails/preparar (HITL)", True, "Prévia formatada com assinatura oficial gerada sob confirmação HITL")
                    else:
                        self.registrar("Endpoints", "POST /api/v1/emails/preparar", False, f"Assinatura ou status incorreto: {dados_dr}")
                else:
                    self.registrar("Endpoints", "POST /api/v1/emails/preparar", False, f"Erro: {r_draft.text}")
            except Exception as e:
                self.registrar("Endpoints", "POST /api/v1/emails/preparar", False, f"Erro: {e}")

    async def testar_gennie_service_do_alfredo(self):
        self.sec_header("4. TESTE DO CLIENTE GennieService DO BOT ALFREDO")
        cliente_alfredo = GennieService(api_url=self.base_url, secret_key=TEST_SECRET)

        # 4.1 Health Check via Client
        saude = await cliente_alfredo.verificar_saude()
        if saude.get("status") == "online":
            self.registrar("GennieService (Alfredo)", "verificar_saude()", True, "Cliente do Alfredo validou com sucesso a conexão com a GENNIE")
        else:
            self.registrar("GennieService (Alfredo)", "verificar_saude()", False, f"Falha no cliente: {saude}")

        # 4.2 Listagem via Client
        res_list = await cliente_alfredo.listar_emails(max_results=2)
        if res_list.get("sucesso") and "emails" in res_list:
            self.registrar("GennieService (Alfredo)", "listar_emails()", True, f"Cliente do Alfredo recuperou {res_list.get('total')} e-mails com sucesso")
        else:
            self.registrar("GennieService (Alfredo)", "listar_emails()", False, f"Falha ao listar: {res_list}")

        # 4.3 Preparação de Rascunho via Client
        res_rasc = await cliente_alfredo.preparar_rascunho("contato@empresa.com", "Orçamento", "Segue orçamento em anexo.")
        if res_rasc.get("sucesso") and res_rasc.get("acao") == "PEDIR_APROVACAO":
            self.registrar("GennieService (Alfredo)", "preparar_rascunho()", True, "Cliente do Alfredo disparou preparação de e-mail com retenção HITL perfeita")
        else:
            self.registrar("GennieService (Alfredo)", "preparar_rascunho()", False, f"Falha no rascunho: {res_rasc}")

    async def testar_tool_enviar_para_alfredo(self):
        self.sec_header("5. TESTE DA TOOL enviar_para_alfredo NO GENNIE")
        # Testa a execução da tool no motor de ferramentas da GENNIE
        user_data = {}
        res_tool = gennie.executar_tool(
            None,
            user_data,
            "enviar_para_alfredo",
            {
                "tipo": "lembrete",
                "conteudo": "Pagar fatura de energia da AWS",
                "data_hora": "2026-09-05 18:00"
            }
        )
        dados_tool = json.loads(res_tool)
        if "Lembrete delegado ao ALFREDO" in dados_tool.get("resultado", ""):
            self.registrar("GENNIE Tool", "enviar_para_alfredo(lembrete)", True, f"Retorno da Tool: {dados_tool['resultado']}")
        else:
            self.registrar("GENNIE Tool", "enviar_para_alfredo(lembrete)", False, f"Resposta inesperada: {res_tool}")

        res_linkedin = gennie.executar_tool(
            None,
            user_data,
            "enviar_para_alfredo",
            {
                "tipo": "linkedin",
                "conteudo": "Relatório semanal sobre agentes autônomos e IA no Gmail."
            }
        )
        dados_lk = json.loads(res_linkedin)
        if "Ghostwriter do ALFREDO" in dados_lk.get("resultado", ""):
            self.registrar("GENNIE Tool", "enviar_para_alfredo(linkedin)", True, f"Retorno da Tool: {dados_lk['resultado']}")
        else:
            self.registrar("GENNIE Tool", "enviar_para_alfredo(linkedin)", False, f"Resposta inesperada: {res_linkedin}")

    async def encerrar(self):
        if self.runner:
            await self.runner.cleanup()

    def exibir_relatorio(self):
        duracao = round(time.time() - self.tempo_inicio, 2)
        total = len(self.resultados)
        sucessos = sum(1 for r in self.resultados if r["status"] == "SUCESSO")
        falhas = sum(1 for r in self.resultados if r["status"] == "FALHA")
        taxa = round((sucessos / total * 100), 1) if total > 0 else 0

        print(f"\n{BOLD}{CYAN}╔═════════════════════════════════════════════════════════════╗{RESET}")
        print(f"{BOLD}{CYAN}║{RESET} {BOLD}{'RELATÓRIO DE VALIDAÇÃO DA PONTE GENNIE <-> ALFREDO'.center(59)} {BOLD}{CYAN}║{RESET}")
        print(f"{BOLD}{CYAN}╠═════════════════════════════════════════════════════════════╣{RESET}")
        print(f"{BOLD}{CYAN}║{RESET}  Tempo de Execução: {BOLD}{duracao}s{RESET}".ljust(69) + f"{BOLD}{CYAN}║{RESET}")
        print(f"{BOLD}{CYAN}║{RESET}  Total de Testes da Ponte: {BOLD}{total}{RESET}".ljust(69) + f"{BOLD}{CYAN}║{RESET}")
        print(f"{BOLD}{CYAN}║{RESET}  🟢 Testes Aprovados: {GREEN}{BOLD}{sucessos}{RESET}".ljust(78) + f"{BOLD}{CYAN}║{RESET}")
        print(f"{BOLD}{CYAN}║{RESET}  🔴 Falhas Detectadas: {RED if falhas > 0 else GREEN}{BOLD}{falhas}{RESET}".ljust(78) + f"{BOLD}{CYAN}║{RESET}")
        print(f"{BOLD}{CYAN}║{RESET}  📊 Taxa de Conformidade: {GREEN if falhas == 0 else RED}{BOLD}{taxa}%{RESET}".ljust(78) + f"{BOLD}{CYAN}║{RESET}")
        print(f"{BOLD}{CYAN}╚═════════════════════════════════════════════════════════════╝{RESET}\n")

        if falhas == 0:
            print(f"{BOLD}{GREEN}🎉 [PONTE 100% OPERACIONAL] GENNIE BOT E BOT ALFREDO ESTÃO PERFEITAMENTE INTEGRADOS!{RESET}\n")
        else:
            print(f"{BOLD}{RED}⚠️ Foram detectadas falhas na validação da ponte. Verifique os logs.{RESET}\n")


async def main():
    validador = ValidadorPonte()
    try:
        await validador.iniciar_servidor_teste()
        await validador.testar_seguranca_e_autenticacao()
        await validador.testar_endpoints_rest()
        await validador.testar_gennie_service_do_alfredo()
        await validador.testar_tool_enviar_para_alfredo()
    finally:
        await validador.encerrar()
    validador.exibir_relatorio()


if __name__ == "__main__":
    asyncio.run(main())
