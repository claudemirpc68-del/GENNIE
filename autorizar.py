from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

BASE = Path(__file__).resolve().parent
CLIENT_SECRET = BASE / "client_secret.json"
TOKEN_FILE = BASE / "token.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
creds = flow.run_local_server(
    port=0,
    authorization_prompt_message="Autorize o acesso ao Gmail no navegador e volte aqui.",
)
TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
print("Autorização concluída. token.json salvo em", TOKEN_FILE)
