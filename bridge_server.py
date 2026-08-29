"""
====================================================================
GENNIE BOT - Servidor de Ponte REST (Bridge Server) para o BOT ALFREDO
====================================================================
Expõe uma API HTTP assíncrona leve usando aiohttp.web para que o BOT ALFREDO
possa consultar e-mails, obter briefings diários, preparar rascunhos e trocar
eventos de forma segura e com baixa latência.
====================================================================
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from aiohttp import web
import httpx

# Garante import do gennie caso executado diretamente
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import gennie

logger = logging.getLogger("GennieBridge")

# Variáveis globais da ponte
BRIDGE_PORT = int(os.environ.get("BRIDGE_PORT", 8000))
BRIDGE_HOST = os.environ.get("BRIDGE_HOST", "0.0.0.0")
BRIDGE_SECRET_KEY = os.environ.get("BRIDGE_SECRET_KEY", "gennie_alfredo_secret_token_2026")
ALFREDO_API_URL = os.environ.get("ALFREDO_API_URL", "http://127.0.0.1:8080")


@web.middleware
async def autenticacao_middleware(request: web.Request, handler):
    """Valida o cabeçalho Authorization: Bearer <BRIDGE_SECRET_KEY> em rotas protegidas."""
    # Rotas públicas
    if request.path in ("/health", "/", "/api/v1/status"):
        return await handler(request)

    # Se a rota começa com /api/v1/, exige autenticação
    if request.path.startswith("/api/v1/"):
        auth_header = request.headers.get("Authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header.split("Bearer ", 1)[1].strip()

        if not token or token != BRIDGE_SECRET_KEY:
            logger.warning(f"Tentativa de acesso não autorizado à ponte em {request.path} de {request.remote}")
            return web.json_response(
                {
                    "sucesso": False,
                    "erro": "Não autorizado. Token de autenticação da ponte ausente ou inválido.",
                    "status_code": 401
                },
                status=401
            )

    return await handler(request)


# ── Rotas da API ─────────────────────────────────────────────────────────────

async def handle_health(request: web.Request) -> web.Response:
    """Health check simples e status da ponte."""
    return web.json_response({
        "status": "online",
        "bot": "GENNIE_BOT",
        "versao": "1.2.0",
        "dono_id": gennie.DONO_ID,
        "conta_email": gennie.CONTA
    })


def obter_service_gmail():
    """Obtém o serviço do Gmail, permitindo override para testes e fallbacks."""
    if hasattr(gennie, "_mock_service_override") and gennie._mock_service_override:
        return gennie._mock_service_override
    return gennie.get_gmail_service()


async def handle_status(request: web.Request) -> web.Response:
    """Retorna o status detalhado da conexão com o Gmail e do bot."""
    gmail_ok = False
    perfil_info = None
    try:
        service = obter_service_gmail()
        perfil = service.users().getProfile(userId="me").execute()
        gmail_ok = True
        perfil_info = {
            "email": perfil.get("emailAddress"),
            "total_mensagens": perfil.get("messagesTotal"),
            "total_threads": perfil.get("threadsTotal")
        }
    except Exception as e:
        logger.warning(f"Verificação de status do Gmail falhou: {e}")

    return web.json_response({
        "sucesso": True,
        "bot": "GENNIE_BOT",
        "gmail_conectado": gmail_ok,
        "perfil": perfil_info,
        "llm_model": gennie.MODEL
    })


async def handle_listar_emails(request: web.Request) -> web.Response:
    """
    Lista e-mails recentes com suporte a query e limite.
    GET /api/v1/emails/recentes?query=in:inbox&max_results=5
    """
    query = request.query.get("query", "in:inbox")
    try:
        max_results = int(request.query.get("max_results", 5))
    except ValueError:
        max_results = 5

    try:
        service = obter_service_gmail()
        emails = gennie.listar_emails(service, query=query, max_results=max_results)
        return web.json_response({
            "sucesso": True,
            "query": query,
            "total": len(emails),
            "emails": emails
        })
    except Exception as e:
        logger.exception("Erro ao listar e-mails via Bridge")
        return web.json_response({"sucesso": False, "erro": str(e)}, status=500)


async def handle_briefing(request: web.Request) -> web.Response:
    """
    Retorna o briefing estruturado dos e-mails recentes para o Alfredo incluir no /boletim.
    GET /api/v1/emails/briefing?query=in:inbox is:unread&max_emails=8
    """
    query = request.query.get("query", "in:inbox is:unread")
    try:
        max_emails = int(request.query.get("max_emails", 8))
    except ValueError:
        max_emails = 8

    try:
        service = obter_service_gmail()
        lote = gennie.obter_lote_para_briefing(service, max_emails=max_emails, query=query)
        
        # Sintetiza com LLM se solicitado
        gerar_sintese = request.query.get("sintetizar", "true").lower() == "true"
        sintese_texto = ""
        
        if gerar_sintese and lote:
            prompt_briefing = [
                {"role": "system", "content": gennie.SYSTEM_PROMPT},
                {"role": "user", "content": f"Elabore um resumo executivo claro e escaneável dos seguintes e-mails recentes para o boletim diário:\n{json.dumps(lote, ensure_ascii=False)}"}
            ]
            try:
                resp_ia = gennie.chamar_deepseek(prompt_briefing)
                sintese_texto = resp_ia["choices"][0]["message"].get("content", "").strip()
            except Exception as e_ia:
                logger.warning(f"Falha ao gerar síntese de briefing com LLM: {e_ia}")

        return web.json_response({
            "sucesso": True,
            "total_analisados": len(lote),
            "sintese_executiva": sintese_texto,
            "emails": lote
        })
    except Exception as e:
        logger.exception("Erro ao gerar briefing via Bridge")
        return web.json_response({"sucesso": False, "erro": str(e)}, status=500)


async def handle_ler_email(request: web.Request) -> web.Response:
    """
    Lê o conteúdo completo de um e-mail pelo ID.
    GET /api/v1/emails/ler?msg_id=19bae30da4cb2ea5
    """
    msg_id = request.query.get("msg_id")
    if not msg_id:
        return web.json_response({"sucesso": False, "erro": "Parâmetro 'msg_id' é obrigatório."}, status=400)

    try:
        service = obter_service_gmail()
        email_detalhe = gennie.ler_email(service, msg_id)
        return web.json_response({
            "sucesso": True,
            "email": email_detalhe
        })
    except Exception as e:
        logger.exception(f"Erro ao ler e-mail {msg_id} via Bridge")
        return web.json_response({"sucesso": False, "erro": str(e)}, status=500)


async def handle_preparar_rascunho(request: web.Request) -> web.Response:
    """
    Prepara uma prévia de e-mail solicitada pelo Alfredo (HITL obrigatório).
    POST /api/v1/emails/preparar
    Body: {"dest": "...", "assunto": "...", "corpo": "..."}
    """
    try:
        dados = await request.json()
    except Exception:
        return web.json_response({"sucesso": False, "erro": "Body JSON inválido."}, status=400)

    dest = dados.get("dest")
    assunto = dados.get("assunto", "(sem assunto)")
    corpo = dados.get("corpo", "")

    if not dest or not corpo:
        return web.json_response({"sucesso": False, "erro": "'dest' e 'corpo' são obrigatórios."}, status=400)

    corpo_formatado = gennie.formatar_corpo_com_assinatura(corpo)
    previa = (
        f"📩 *Prévia do E-mail (Solicitado via Alfredo)*\n\n"
        f"👤 *Para:* `{dest}`\n"
        f"📌 *Assunto:* {assunto}\n\n"
        f"📝 *Mensagem:*\n{corpo_formatado}\n\n"
        f"⚠️ _Aprovado para envio sob confirmação Human-in-the-Loop._"
    )

    return web.json_response({
        "sucesso": True,
        "acao": "PEDIR_APROVACAO",
        "previa_formatada": previa,
        "draft": {
            "dest": dest,
            "assunto": assunto,
            "corpo": corpo_formatado
        }
    })


async def handle_delegar_para_alfredo(request: web.Request) -> web.Response:
    """
    Endpoint para envio de eventos da GENNIE para o Alfredo (ex: lembretes ou ghostwriting).
    POST /api/v1/bridge/delegar_alfredo
    Body: {"tipo": "lembrete" | "linkedin", "conteudo": "...", "data_hora": "..."}
    """
    try:
        dados = await request.json()
    except Exception:
        return web.json_response({"sucesso": False, "erro": "Body JSON inválido."}, status=400)

    tipo = dados.get("tipo", "lembrete")
    conteudo = dados.get("conteudo", "")
    data_hora = dados.get("data_hora", "")

    headers = {
        "Authorization": f"Bearer {BRIDGE_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "origem": "GENNIE_BOT",
        "tipo": tipo,
        "conteudo": conteudo,
        "data_hora": data_hora
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{ALFREDO_API_URL}/api/v1/webhook/gennie", json=payload, headers=headers)
            if resp.status_code in (200, 201):
                return web.json_response({"sucesso": True, "resposta_alfredo": resp.json()})
            else:
                return web.json_response({"sucesso": False, "erro_alfredo": resp.text, "status_code": resp.status_code}, status=502)
    except Exception as e:
        logger.warning(f"Não foi possível contatar o Alfredo em {ALFREDO_API_URL}: {e}")
        return web.json_response({
            "sucesso": False,
            "aviso": "Evento registrado localmente, mas o servidor do Alfredo não respondeu no momento.",
            "detalhe": str(e)
        }, status=503)


# ── Inicialização do Servidor ────────────────────────────────────────────────

def criar_app_bridge() -> web.Application:
    """Cria e configura a aplicação aiohttp com rotas e middlewares."""
    gennie.carregar_env()
    app = web.Application(middlewares=[autenticacao_middleware])

    # Rotas
    app.router.add_get("/", handle_health)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/api/v1/status", handle_status)
    app.router.add_get("/api/v1/emails/recentes", handle_listar_emails)
    app.router.add_get("/api/v1/emails/briefing", handle_briefing)
    app.router.add_get("/api/v1/emails/ler", handle_ler_email)
    app.router.add_post("/api/v1/emails/preparar", handle_preparar_rascunho)
    app.router.add_post("/api/v1/bridge/delegar_alfredo", handle_delegar_para_alfredo)

    return app


async def iniciar_servidor_bridge(host: str = BRIDGE_HOST, port: int = BRIDGE_PORT):
    """Inicia o servidor aiohttp como corrotina assíncrona."""
    app = criar_app_bridge()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info(f"🚀 Bridge Server da GENNIE ativo em http://{host}:{port}")
    return runner


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)-12s | %(levelname)-7s | %(message)s")
    print(f"Iniciando Bridge Server da GENNIE na porta {BRIDGE_PORT}...")
    app = criar_app_bridge()
    web.run_app(app, host=BRIDGE_HOST, port=BRIDGE_PORT)
