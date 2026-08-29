# 🌉 Manual de Integração: BOT ALFREDO & GENNIE BOT

Este guia fornece o passo a passo exato para conectar o seu **BOT ALFREDO** (no Coolify / GitHub) com o **GENNIE BOT**.

---

## 📦 Arquivos Prontos para Copiar para o BOT_ALFREDO

Todos os arquivos necessários foram gerados e organizados na pasta `alfredo_package/`:

| Arquivo Origem (neste workspace) | Destino no Repositório do BOT_ALFREDO |
| :--- | :--- |
| `alfredo_package/SKILLS ALFREDO/email.py` | `SKILLS ALFREDO/email.py` |
| `alfredo_package/bot/services/gennie_service.py` | `bot/services/gennie_service.py` |
| `alfredo_package/bot/handlers/email_handler.py` | `bot/handlers/email_handler.py` |

---

## ⚙️ 1. Variáveis de Ambiente no Coolify (BOT_ALFREDO)

No painel do **Coolify** (ou no arquivo `.env` do Alfredo), adicione as seguintes variáveis:

```env
# ── Integração com a GENNIE BOT ──
GENNIE_API_URL=http://<IP_OU_DOMINIO_DA_GENNIE>:8000
GENNIE_BRIDGE_KEY=gennie_alfredo_secret_token_2026
```

*(Se ambos estiverem no mesmo servidor Coolify na mesma rede Docker, a `GENNIE_API_URL` pode ser o nome do container ou `http://gennie:8000`)*.

---

## 📝 2. Atualização no `bot/main.py` do ALFREDO

Abra o arquivo `bot/main.py` no repositório do **BOT_ALFREDO** e faça duas pequenas edições:

### A) No `post_init` (Inicialização do Serviço da GENNIE):
```python
    # ── Serviço GENNIE (E-mails & Gmail) ──
    from bot.services.gennie_service import GennieService
    from bot.config import os
    gennie = GennieService()
    application.bot_data["gennie"] = gennie
```

### B) No Registro de Comandos e Handlers:
```python
    # Importe o handler de e-mails
    from bot.handlers.email_handler import email_command

    # Adicione ao menu autocompletar de comandos
    commands.append(BotCommand("email", "Consultar e-mails e briefings da GENNIE"))

    # Registre o CommandHandler no app
    app.add_handler(CommandHandler(("email", "emails"), email_command))
```

---

## ☕ 3. Enriquecer o `/boletim` com os E-mails da GENNIE (Boletim 360°)

No handler do `/boletim` (no arquivo `bot/handlers/tools.py`), você pode incluir o briefing da GENNIE:

```python
async def boletim_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... código existente de notícias e dólar ...
    
    # Consulta a GENNIE para adicionar os e-mails ao boletim matinal
    gennie: GennieService = context.bot_data.get("gennie")
    bloco_emails = ""
    if gennie:
        try:
            brief = await gennie.obter_briefing(max_emails=4, sintetizar=True)
            if brief.get("sucesso") and brief.get("sintese_executiva"):
                bloco_emails = f"\n\n📬 *Seus E-mails (via GENNIE):*\n{brief['sintese_executiva']}"
        except Exception:
            pass

    mensagem_final = f"{boletim_noticias_e_cotacao}{bloco_emails}"
    await update.effective_message.reply_text(mensagem_final, parse_mode="Markdown")
```

---

## 🚀 4. Novos Comandos Disponíveis no ALFREDO

Depois de aplicar:
* `/email` ➔ Exibe os 3 e-mails mais recentes com indicador de não lidos.
* `/email nao-lidos` ➔ Filtra mensagens não lidas.
* `/email briefing` ➔ Exibe o resumo executivo completo do dia.
* `/email ler <id>` ➔ Lê o conteúdo e exibe os anexos do e-mail.
* *"Alfredo, o financeiro me mandou algum e-mail hoje?"* ➔ O Alfredo entende via Skill e consulta a GENNIE!
