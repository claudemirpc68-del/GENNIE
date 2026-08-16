import asyncio
import sys
import gennie

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

gennie.carregar_env()
service = gennie.get_gmail_service()

interacoes = [
    "Oi GENNIE, tudo bem?",
    "Muito obrigado pela ajuda!",
    "Você é muito rápido, valeu mesmo!",
    "Tem mais alguma coisa pendente?"
]

async def testar_dialogo():
    user_data = {}
    print("=== TESTE DE DIÁLOGO NATURAL E CONTINUIDADE ===")
    for msg in interacoes:
        print(f"\n👤 Usuário: \"{msg}\"")
        resposta = await gennie.agente_llm(service, user_data, msg)
        print(f"🤖 GENNIE: {resposta}")

if __name__ == "__main__":
    asyncio.run(testar_dialogo())
