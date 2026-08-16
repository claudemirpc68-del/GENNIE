import asyncio
import json
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

cenarios = [
    {
        "titulo": "Cenário 1: Listagem de e-mails",
        "entrada": "Tem algum e-mail novo na minha caixa de entrada?",
    },
    {
        "titulo": "Cenário 2: Leitura de e-mail específico",
        "entrada": "Leia o conteúdo do e-mail 1a007f8eb8186285",
    },
    {
        "titulo": "Cenário 3: Preparação de Resposta com Trava de Segurança",
        "entrada": "Responda ao e-mail 1a007f8eb8186285 confirmando que já realizei a checagem do cadastro.",
    },
    {
        "titulo": "Cenário 4: Criação de Novo E-mail com Trava de Segurança",
        "entrada": "Envie um e-mail para financeiro@empresa.com com assunto 'Envio de Comprovante' e corpo 'Segue o comprovante em anexo, obrigado.'",
    }
]

async def rodar_simulacoes():
    print("==================================================")
    print("🚀 INICIANDO TESTES INTERATIVOS DAS FUNCIONALIDADES")
    print("==================================================\n")

    user_data = {}
    
    for c in cenarios:
        print(f"\n--- {c['titulo']} ---")
        print(f"👤 Usuário: \"{c['entrada']}\"")
        resposta = await gennie.agente_llm(service, user_data, c['entrada'])
        print(f"\n🤖 GENNIE Resposta:\n{resposta}")
        if "draft" in user_data:
            print(f"\n🔒 Trava de Segurança Ativada no context.user_data:")
            print(json.dumps(user_data["draft"], indent=2, ensure_ascii=False))
            user_data.pop("draft", None)
        print("\n" + "=" * 50)

if __name__ == "__main__":
    asyncio.run(rodar_simulacoes())
