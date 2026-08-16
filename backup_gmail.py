import base64
import json
import sys
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

BASE = Path(__file__).resolve().parent
TOKEN_FILE = BASE / "token.json"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def get_service():
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
    if not creds.valid:
        creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)


def corpo_do_email(payload):
    if payload.get("body", {}).get("data"):
        try:
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
        except Exception:
            return ""
    for p in payload.get("parts", []):
        if p.get("mimeType") == "text/plain" and p.get("body", {}).get("data"):
            try:
                return base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", errors="replace")
            except Exception:
                return ""
    return ""


def main():
    service = get_service()
    backup = []
    pagina = None
    total = 0
    while True:
        req = service.users().messages().list(userId="me", maxResults=200, pageToken=pagina)
        res = req.execute()
        msgs = res.get("messages", [])
        for m in msgs:
            try:
                det = service.users().messages().get(
                    userId="me", id=m["id"], format="full"
                ).execute()
                headers = {h["name"].lower(): h["value"] for h in det.get("payload", {}).get("headers", [])}
                backup.append({
                    "id": det["id"],
                    "thread_id": det.get("threadId"),
                    "from": headers.get("from", ""),
                    "to": headers.get("to", ""),
                    "subject": headers.get("subject", ""),
                    "date": headers.get("date", ""),
                    "labels": det.get("labelIds", []),
                    "corpo": corpo_do_email(det.get("payload", {})),
                })
                total += 1
            except Exception as e:
                print(f"ERRO ao ler {m['id']}: {e}")
            if total % 100 == 0:
                print(f"{total} emails salvos...", flush=True)
        pagina = res.get("nextPageToken")
        if not pagina:
            break

    agora = datetime.now().strftime("%Y%m%d_%H%M%S")
    arq = BASE / f"backup_emails_{agora}.json"
    arq.write_text(json.dumps(backup, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nBACKUP CONCLUIDO: {total} emails salvos em {arq}")


if __name__ == "__main__":
    main()
